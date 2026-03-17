import re
import os
import json
import random
import time as _time
import sys
import subprocess

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

# ── Transformers version check ────────────────────────────────────────────────
# Qwen3.5 requires transformers >= 4.43.0 for full performance and correct
# chat template support. Older versions are significantly slower and may
# produce degraded output. Auto-upgrade if needed.
_TRANSFORMERS_MIN = (4, 43, 0)
_TRANSFORMERS_MIN_STR = "4.43.0"

def _check_and_upgrade_transformers():
    try:
        import transformers as _tf
        _ver = tuple(int(x) for x in _tf.__version__.split(".")[:3])
        if _ver >= _TRANSFORMERS_MIN:
            print(f"[LTX2-Qwen] transformers {_tf.__version__} — OK")
            return
        print(f"[LTX2-Qwen] transformers {_tf.__version__} is outdated "
              f"(need >= {_TRANSFORMERS_MIN_STR}). Upgrading...")
    except ImportError:
        print(f"[LTX2-Qwen] transformers not found. Installing...")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install",
             f"transformers>={_TRANSFORMERS_MIN_STR}",
             "--upgrade", "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Force reload so the rest of the file gets the updated version
        if "transformers" in sys.modules:
            import importlib
            import transformers as _tf2
            importlib.reload(_tf2)
        print(f"[LTX2-Qwen] transformers upgraded successfully. "
              f"Restart ComfyUI if you encounter any issues.")
    except Exception as e:
        print(f"[LTX2-Qwen] WARNING: Could not upgrade transformers automatically: {e}. "
              f"Please run: pip install transformers>={_TRANSFORMERS_MIN_STR} --upgrade")

_check_and_upgrade_transformers()

import torch
import gc
from transformers import AutoModelForCausalLM, AutoTokenizer


# ── Audio analysis ────────────────────────────────────────────────────────────

def _analyse_audio(audio_dict, use_whisper: bool) -> dict:
    """
    Takes a ComfyUI AUDIO dict {waveform: Tensor[C,N], sample_rate: int}
    Returns a plain dict describing the audio for injection into the LLM prompt.
    whisper transcription only runs if use_whisper=True.
    """
    result = {
        "duration_s":    None,
        "energy_shape":  None,   # quiet / building / constant / explosive / fading
        "tempo_feel":    None,   # slow / moderate / fast / very_fast / no_beat
        "freq_character":None,   # bass_heavy / balanced / bright / vocal_dominant
        "has_speech":    False,
        "transcript":    None,
        "speech_tone":   None,   # whispered / conversational / elevated / shouting
        "silence_ratio": None,   # 0.0–1.0 fraction of clip that is near-silence
        "peak_moment":   None,   # seconds into clip where loudest moment occurs
        "summary":       None,   # plain English summary for LLM injection
    }

    try:
        import numpy as np
        waveform    = audio_dict.get("waveform")
        sample_rate = audio_dict.get("sample_rate", 44100)

        if waveform is None:
            return result

        # Tensor → numpy mono  (detach + cpu required for gradient-tracked / CUDA tensors)
        if hasattr(waveform, "detach"):
            wav = waveform.detach().cpu().numpy()
        elif hasattr(waveform, "numpy"):
            wav = waveform.numpy()
        else:
            wav = np.array(waveform)

        # Handle [batch, channels, samples] from ComfyUI VHS
        if wav.ndim == 3:
            wav = wav[0]
        if wav.ndim == 2:
            wav = wav.mean(axis=0)
        wav = wav.astype(np.float32)

        n_samples = len(wav)
        duration  = n_samples / sample_rate
        result["duration_s"] = round(duration, 2)

        # ── RMS energy over 100ms windows ──────────────────────────────
        win     = int(sample_rate * 0.1)
        hop     = win // 2
        frames  = [wav[i:i+win] for i in range(0, n_samples - win, hop)]
        rms     = np.array([np.sqrt(np.mean(f**2 + 1e-9)) for f in frames])
        rms_db  = 20 * np.log10(rms + 1e-9)

        peak_frame   = int(np.argmax(rms))
        result["peak_moment"] = round(peak_frame * hop / sample_rate, 2)

        # Silence ratio — anchored to an absolute floor so loud/constant-energy audio
        # doesn't incorrectly report ~20% silence due to the relative percentile trick.
        SILENCE_FLOOR_DB   = -50.0   # anything quieter than this is silence
        silence_ratio      = float(np.mean(rms_db < SILENCE_FLOOR_DB))
        result["silence_ratio"] = round(silence_ratio, 2)

        # Energy shape — compare first third vs last third vs peak
        third   = len(rms) // 3
        e_start = float(np.mean(rms[:third]))
        e_mid   = float(np.mean(rms[third:2*third]))
        e_end   = float(np.mean(rms[2*third:]))
        e_peak  = float(np.max(rms))
        e_mean  = float(np.mean(rms))

        if e_peak > e_mean * 2.5 and peak_frame > third:
            result["energy_shape"] = "builds to explosive peak"
        elif e_start > e_end * 1.4:
            result["energy_shape"] = "loud then fading"
        elif e_end > e_start * 1.4:
            result["energy_shape"] = "builds throughout"
        elif silence_ratio > 0.4:
            result["energy_shape"] = "sparse with long silences"
        elif np.std(rms) / (e_mean + 1e-9) < 0.3:
            result["energy_shape"] = "constant sustained energy"
        else:
            result["energy_shape"] = "varied dynamic range"

        # ── Tempo / beat detection via RMS onset strength ──────────────
        from scipy.signal import find_peaks
        onset_env = np.diff(rms, prepend=rms[0])
        onset_env = np.maximum(onset_env, 0)
        min_dist  = int(0.3 / (hop / sample_rate))   # min 300ms between beats
        peaks, _  = find_peaks(onset_env, height=np.mean(onset_env)*1.2, distance=min_dist)

        if len(peaks) > 2:
            intervals_s = np.diff(peaks) * hop / sample_rate
            avg_bpm     = 60.0 / np.median(intervals_s)
            if avg_bpm < 60:
                result["tempo_feel"] = f"slow ({int(avg_bpm)} bpm)"
            elif avg_bpm < 100:
                result["tempo_feel"] = f"moderate ({int(avg_bpm)} bpm)"
            elif avg_bpm < 140:
                result["tempo_feel"] = f"fast ({int(avg_bpm)} bpm)"
            else:
                result["tempo_feel"] = f"very fast ({int(avg_bpm)} bpm)"
        else:
            result["tempo_feel"] = "no clear beat / ambient"

        # ── Frequency character via FFT on full clip ───────────────────
        fft_size  = min(n_samples, 65536)
        spectrum  = np.abs(np.fft.rfft(wav[:fft_size]))
        freqs     = np.fft.rfftfreq(fft_size, d=1.0/sample_rate)
        bass_e    = float(np.mean(spectrum[(freqs >= 20)  & (freqs < 300)]))
        mid_e     = float(np.mean(spectrum[(freqs >= 300) & (freqs < 3000)]))
        high_e    = float(np.mean(spectrum[(freqs >= 3000)& (freqs < 8000)]))
        vocal_e   = float(np.mean(spectrum[(freqs >= 200) & (freqs < 3400)]))  # vocal band

        if vocal_e > bass_e * 1.5 and vocal_e > high_e * 1.2:
            result["freq_character"] = "vocal dominant"
        elif bass_e > mid_e * 1.4 and bass_e > high_e * 2:
            result["freq_character"] = "bass heavy"
        elif high_e > bass_e * 1.5 and high_e > mid_e:
            result["freq_character"] = "bright / treble"
        else:
            result["freq_character"] = "balanced full range"

        # ── Whisper transcription ──────────────────────────────────────
        if use_whisper:
            _wmodel = None
            try:
                import whisper as _whisper
                print("[LTX2-Qwen] Whisper: loading tiny model...")
                _wmodel = _whisper.load_model("tiny")
                # Whisper wants float32 mono at 16kHz
                from scipy.signal import resample_poly
                from math import gcd
                target_sr = 16000
                if sample_rate != target_sr:
                    g       = gcd(sample_rate, target_sr)
                    wav_16k = resample_poly(wav, target_sr // g, sample_rate // g).astype(np.float32)
                else:
                    wav_16k = wav
                w_result   = _wmodel.transcribe(wav_16k, fp16=False, language=None)
                transcript = w_result.get("text", "").strip()
                if transcript:
                    result["has_speech"]  = True
                    result["transcript"]  = transcript
                    # Rough tone from amplitude stats during speech segments
                    speech_rms = float(np.mean(np.abs(wav_16k)))
                    if speech_rms < 0.02:
                        result["speech_tone"] = "whispered or very quiet"
                    elif speech_rms < 0.08:
                        result["speech_tone"] = "conversational"
                    elif speech_rms < 0.18:
                        result["speech_tone"] = "elevated / emphatic"
                    else:
                        result["speech_tone"] = "loud / shouting"
                    print(f"[LTX2-Qwen] Whisper transcript: {transcript[:120]}...")
                else:
                    print("[LTX2-Qwen] Whisper: no speech detected")
            except ImportError:
                print("[LTX2-Qwen] Whisper not installed — skipping transcription. pip install openai-whisper")
            except Exception as e:
                print(f"[LTX2-Qwen] Whisper failed (non-fatal): {e}")
            finally:
                # Always offload Whisper — load fresh every run, no caching
                if _wmodel is not None:
                    del _wmodel
                gc.collect()
                try:
                    import torch as _torch
                    if _torch.cuda.is_available():
                        _torch.cuda.empty_cache()
                        _torch.cuda.ipc_collect()
                except Exception:
                    pass
                print("[LTX2-Qwen] Whisper offloaded.")

        # ── Build plain-English summary for LLM ───────────────────────
        parts = []
        parts.append(f"Duration: {result['duration_s']}s.")
        parts.append(f"Energy: {result['energy_shape']}.")
        if result["tempo_feel"]:
            parts.append(f"Rhythm: {result['tempo_feel']}.")
        if result["freq_character"]:
            parts.append(f"Sound character: {result['freq_character']}.")
        if result["peak_moment"] and result["duration_s"]:
            pct = result["peak_moment"] / result["duration_s"]
            parts.append(f"Loudest moment at {result['peak_moment']}s ({int(pct*100)}% through).")
        if result["silence_ratio"] and result["silence_ratio"] > 0.3:
            parts.append(f"Significant silence ({int(result['silence_ratio']*100)}% of clip).")
        if result["has_speech"] and result["transcript"]:
            parts.append(f"Speech detected ({result['speech_tone']}): \"{result['transcript'][:400]}\"")
        elif result["has_speech"]:
            parts.append(f"Speech detected ({result['speech_tone']}) — transcription unavailable.")

        result["summary"] = " ".join(parts)

    except Exception as e:
        print(f"[LTX2-Qwen] Audio analysis failed (non-fatal): {e}")
        result["summary"] = None

    return result


def _build_audio_instruction(audio_analysis: dict) -> str:
    """Converts audio analysis dict into an LLM instruction block."""
    if not audio_analysis or not audio_analysis.get("summary"):
        return ""

    a = audio_analysis
    lines = ["\n[AUDIO ANALYSIS — shape the visuals to match this audio:"]
    lines.append(a["summary"])

    # Specific directives based on what we found
    if a.get("energy_shape") == "builds to explosive peak" and a.get("peak_moment"):
        lines.append(
            f"The audio builds and hits hard at {a['peak_moment']}s — "
            "mirror this: start restrained, escalate, let the visual peak land at the same moment."
        )
    elif a.get("energy_shape") == "sparse with long silences":
        lines.append(
            "The audio is sparse and quiet. Match this: slow camera, minimal action, "
            "let silence breathe in the visual pacing."
        )
    elif a.get("energy_shape") == "constant sustained energy":
        lines.append(
            "Sustained consistent energy throughout — maintain visual intensity evenly, no dramatic arc."
        )
    elif a.get("energy_shape") == "builds throughout":
        lines.append(
            "Energy grows from start to finish — visuals should escalate progressively, "
            "ending more intense than they began."
        )

    if a.get("tempo_feel") and "very fast" in a["tempo_feel"]:
        lines.append("Fast tempo — camera movement and subject action should feel kinetic and driven.")
    elif a.get("tempo_feel") and "slow" in a["tempo_feel"]:
        lines.append("Slow tempo — deliberate camera movement, held shots, unhurried action.")
    elif a.get("tempo_feel") and "no clear beat" in a["tempo_feel"]:
        lines.append("Ambient / no beat — floating camera movement, atmospheric over kinetic.")

    if a.get("freq_character") == "bass heavy":
        lines.append("Heavy bass presence — weight, physicality, and low-frequency movement in the visuals.")
    elif a.get("freq_character") == "bright / treble":
        lines.append("Bright treble character — light, crisp, airy visuals to match.")
    elif a.get("freq_character") == "vocal dominant":
        lines.append("Vocals are the dominant element — frame the speaker, sync lip movement if dialogue is present.")

    if a.get("has_speech") and a.get("transcript"):
        lines.append(
            f"The audio contains speech. If the scene shows a person speaking, "
            f"their words are: \"{a['transcript'][:300]}\". "
            "Sync the visual scene to what is being said — if they describe an action, show it. "
            "If it's a monologue, frame them speaking. Do not invent different dialogue."
        )

    lines.append("]")
    return "\n".join(lines)


# ── Negative prompt ───────────────────────────────────────────────────────────

_NEG_BASE = (
    "watermark, text, signature, duplicate, "
    "static, no motion, frozen, "
    "poorly drawn, bad anatomy, deformed, disfigured, "
    "extra limbs, missing limbs, floating limbs, disconnected body parts, "
    "micro jitter, flickering, strobing, aliasing, high frequency patterns, "
    "motion artifacts, temporal inconsistency, frame stuttering"
)

_NEG_EXPLICIT      = "censored, mosaic, pixelated, black bar, blurred genitals"
_NEG_PORTRAIT_SHOT = "wide angle distortion, fish eye, full body shot"
_NEG_WIDE          = "close-up, portrait crop, tight frame"
_NEG_MULTI         = "merged bodies, fused figures, incorrect number of people"
_NEG_PORTRAIT_ORI  = "landscape orientation, letterbox, pillarbox, horizontal crop, widescreen framing"
_NEG_VHS           = "clean digital, sharp edges, 4K, high resolution, pristine quality"
_NEG_HORROR        = "bright happy lighting, warm tones, cheerful atmosphere, soft light"
_NEG_FASHION       = "casual handheld, amateur footage, flat lighting, unposed"
_NEG_SELFIE        = (
    "tripod, gimbal stabilised, smooth camera movement, rack focus, dolly, crane, "
    "cinematic bokeh, dramatic depth of field, professional lighting, film grain, "
    "colour grade, cinematic lens, landscape orientation"
)
_NEG_ANIME        = "photorealistic, live action, real person, CGI, 3D render, western cartoon, flat shading"
_NEG_2DCARTOON    = "photorealistic, 3D render, CGI, anime, live action, flat digital art, no line work"
_NEG_3DCGI        = "photorealistic, live action, 2D flat, hand-drawn, sketch, anime, watercolour"
_NEG_STOPMOTION   = "smooth motion, CGI, photorealistic, digital, fluid movement, motion blur"
_NEG_COMICBOOK    = "photorealistic, soft gradients, 3D render, painterly, no line art, anime"
_NEG_CELSHADED    = "photorealistic, soft shading, gradients, painterly, hand-drawn lines, anime"
_NEG_ROTOSCOPE    = "fully animated, cartoon, CGI, no live action base, unnatural movement"
_NEG_CYBERPUNK    = "natural lighting, pastoral, warm tones, daylight, photorealistic skin, muted colour"
_NEG_SCIFI        = "medieval, fantasy, nature, pastoral, historical, period costume, warm earthy tones"
_NEG_GRAVURE      = ("dark dramatic lighting, moody shadows, desaturated colour, film noir, cinematic grade, harsh contrast, gritty texture, low key lighting, overcast flat light, ugly, deformed, bad anatomy")


def _build_negative_prompt(result: str, user_input: str, is_portrait: bool = False, style_preset: str = "") -> str:
    combined = (result + " " + user_input + " " + style_preset).lower()
    extras = []

    # Explicit content — suppress censorship artifacts
    if any(w in combined for w in ["pussy", "cock", "penis", "vagina", "nude", "naked", "explicit", "nipple", "breast"]):
        extras.append(_NEG_EXPLICIT)

    # Shot framing conflicts
    if any(w in combined for w in ["close-up", "close up", "face shot", "headshot"]):
        extras.append(_NEG_PORTRAIT_SHOT)
    elif any(w in combined for w in ["wide shot", "wide angle", "aerial", "bird's-eye", "establishing"]):
        extras.append(_NEG_WIDE)

    if any(w in combined for w in ["two women", "two men", "two people", "both", "together", "couple", "they "]):
        extras.append(_NEG_MULTI)

    if is_portrait or "portrait vertical" in style_preset.lower() or "9:16" in style_preset:
        extras.append(_NEG_PORTRAIT_ORI)

    if "lo-fi" in style_preset.lower() or "vhs" in style_preset.lower():
        extras.append(_NEG_VHS)
    if "horror" in style_preset.lower():
        extras.append(_NEG_HORROR)
    if "fashion editorial" in style_preset.lower():
        extras.append(_NEG_FASHION)
    if "selfie" in style_preset.lower() or "self-shot" in style_preset.lower():
        extras.append(_NEG_SELFIE)

    if "anime" in style_preset.lower():
        extras.append(_NEG_ANIME)
    if "2d cartoon" in style_preset.lower():
        extras.append(_NEG_2DCARTOON)
    if "3d cgi" in style_preset.lower():
        extras.append(_NEG_3DCGI)
    if "stop motion" in style_preset.lower():
        extras.append(_NEG_STOPMOTION)
    if "comic book" in style_preset.lower():
        extras.append(_NEG_COMICBOOK)
    if "cel-shaded" in style_preset.lower():
        extras.append(_NEG_CELSHADED)
    if "rotoscope" in style_preset.lower():
        extras.append(_NEG_ROTOSCOPE)
    if "cyberpunk" in style_preset.lower():
        extras.append(_NEG_CYBERPUNK)
    if "sci-fi" in style_preset.lower():
        extras.append(_NEG_SCIFI)
    if "gravure" in style_preset.lower():
        extras.append(_NEG_GRAVURE)

    parts = [p for p in [_NEG_BASE] + extras if p.strip()]
    return ", ".join(parts)


# ── Character attribute pools ─────────────────────────────────────────────────

_CHAR_AGES = [
    # Range: 18–21. Weighted toward 19–20 as peak youth.
    # Duplicates are intentional weighting — not a mistake.
    "18",
    "19", "19", "19",
    "20", "20", "20",
    "21", "21",
]

_CHAR_AGES_ADULT = _CHAR_AGES  # all entries already 18+

_CHAR_ETHNICITIES_FEMALE = [
    # ── White — dominant (12 entries) ───────────────────────────────────────
    ("White",            "pale freckled skin with pink undertones"),
    ("White",            "fair skin with cool undertones"),
    ("White",            "light skin with warm peachy tones"),
    ("White",            "porcelain skin with visible blue veins at the temples"),
    ("White",            "fair skin with a light golden summer tan"),
    ("White",            "light skin with a soft rosy flush across the cheeks"),
    ("White",            "pale skin with cool blue-pink undertones"),
    ("White",            "creamy fair skin with warm neutral undertones"),
    ("White",            "light skin, slightly olive-toned from sun exposure"),
    ("White",            "fair freckled skin with warm amber undertones"),
    ("White",            "light skin with warm honey undertones"),
    ("White",            "fair skin, slightly flushed at the cheeks"),
    # ── East Asian — strong secondary (10 entries) ───────────────────────────
    ("Japanese",         "pale skin with cool beige undertones"),
    ("Korean",           "fair skin with a soft peachy-pink flush"),
    ("Chinese",          "light golden-toned skin"),
    ("East Asian",       "fair cool-toned skin with a subtle pink undertone"),
    ("East Asian",       "light ivory skin with warm golden undertones"),
    ("Japanese",         "very fair skin, almost translucent in soft light"),
    ("Korean",           "smooth fair skin with a cool porcelain tone"),
    ("Chinese",          "warm ivory skin with golden undertones"),
    ("East Asian",       "pale skin with a subtle warm peach cast"),
    ("East Asian",       "light skin with cool neutral undertones and a natural glow"),
    # ── Black — rare (2 entries only) ────────────────────────────────────────
    ("Black",            "deep ebony skin with cool blue-black undertones"),
    ("Black",            "medium warm brown skin with golden undertones"),
]

# Male pool — mostly White, some East Asian, very rare Black
_CHAR_ETHNICITIES_MALE = [
    # ── White — dominant (10 entries) ───────────────────────────────────────
    ("White",            "fair skin with cool undertones"),
    ("White",            "light skin with warm peachy tones"),
    ("White",            "fair skin with a light golden summer tan"),
    ("White",            "light skin, slightly olive-toned from sun exposure"),
    ("White",            "fair freckled skin with warm amber undertones"),
    ("White",            "light skin with warm honey undertones"),
    ("White",            "creamy fair skin with warm neutral undertones"),
    ("White",            "pale skin with cool blue-pink undertones"),
    ("White",            "fair skin, slightly flushed at the cheeks"),
    ("White",            "pale freckled skin with pink undertones"),
    # ── East Asian — secondary (4 entries) ──────────────────────────────────
    ("Japanese",         "pale skin with cool beige undertones"),
    ("Korean",           "fair skin with a soft peachy-pink flush"),
    ("East Asian",       "light golden-toned skin with warm undertones"),
    ("East Asian",       "light skin with cool neutral undertones"),
    # ── Black — rare (1 entry) ───────────────────────────────────────────────
    ("Black",            "medium warm brown skin with golden undertones"),
]

# Legacy alias — points to female pool; kept so any external code referencing
# _CHAR_ETHNICITIES still works. Must be defined AFTER both lists above.
_CHAR_ETHNICITIES = _CHAR_ETHNICITIES_FEMALE

# ── Hair colour pools ─────────────────────────────────────────────────────────
# Split by ethnicity group so colours are always plausible.
# Grey is age-gated inside _build_char_seed — never picked randomly for under-40s.

# East Asian — almost always dark, occasional dyed
_CHAR_HAIR_COLOURS_EAST_ASIAN = [
    "jet black", "jet black", "jet black", "jet black", "jet black",
    "dark brown", "dark brown",
    "blue-black", "blue-black",
    "natural dark brown with caramel highlights",
    "dyed burgundy",
    "dyed bleach blonde with dark roots",
]

# White — full natural range plus occasional dyed
_CHAR_HAIR_COLOURS_WHITE = [
    "dark brown", "dark brown",
    "warm medium brown", "warm medium brown",
    "warm chestnut brown",
    "honey blonde", "honey blonde",
    "ash blonde",
    "strawberry blonde",
    "auburn",
    "copper red",
    "platinum blonde",
    "natural dark brown with caramel highlights",
    "dyed burgundy",
    "dyed bleach blonde with dark roots",
]

# Dark — for Black, South Asian, Indian, Southeast Asian, Middle Eastern, Latina, mixed
_CHAR_HAIR_COLOURS_DARK = [
    "jet black", "jet black", "jet black",
    "dark brown", "dark brown",
    "warm medium brown",
    "blue-black",
    "natural dark brown with caramel highlights",
    "warm chestnut brown",
    "dyed burgundy",
]

# Grey — age-gated, only used 40+
_CHAR_HAIR_COLOURS_GREY = [
    "silver-streaked dark brown",
    "salt-and-pepper grey",
    "silver-white",
]

# ── Hair style pools ───────────────────────────────────────────────────────────
# Ethnicity-aware so we don't get East Asian women with cornrows or afros

_CHAR_HAIR_STYLES_STRAIGHT = [
    # East Asian, White — straight/wavy textures
    "pin-straight, very long, falling to the waist",
    "pin-straight, blunt cut to the shoulder",
    "sleek straight hair, cut to the chin",
    "straight with a heavy blunt fringe",
    "loose beach waves, mid-back length",
    "tousled waves, shoulder-length",
    "soft waves with a side part, collarbone length",
    "chin-length bob, blunt",
    "asymmetric bob, longer on one side",
    "high ponytail, sleek",
    "messy bun with loose strands framing the face",
    "half-up half-down, loosely pinned",
    "low bun, tight and smooth",
    "very long straight hair, centre-parted",
    "long layered hair with curtain bangs",
    "long thick hair in a loose braid over one shoulder",
    "cropped pixie cut, textured",
    "short sleek crop, close to the head",
    "shoulder-length with soft layers",
    "long straight hair with wispy curtain bangs",
]

_CHAR_HAIR_STYLES_CURLY = [
    # Latina, Middle Eastern, mixed race, South Asian, Indian — wavy/curly textures
    "loose 3B curls, mid-length",
    "defined 3C ringlets, shoulder-length",
    "big loose natural curls, voluminous",
    "tousled waves, shoulder-length",
    "long thick curly hair, loosely tied back",
    "curly bob, chin-length",
    "long curly hair with a centre part",
    "half-up half-down, loose curls falling forward",
    "high ponytail of loose curls",
    "long wavy hair with a side part",
    "messy bun of loose curls with strands framing the face",
    "long dark hair in a loose plait over one shoulder",
    "thick straight hair with a blunt fringe",
    "sleek high bun, tight",
]

_CHAR_HAIR_STYLES_TEXTURED = [
    # Black, African ethnicities — natural textured hair
    "tight 4C coils, natural and full",
    "thick natural afro, rounded",
    "big loose natural curls, voluminous",
    "long box braids falling past the shoulders",
    "short box braids, chin-length",
    "thick cornrows flat to the scalp",
    "two-strand twists, loose and mid-length",
    "high bun of twisted locs",
    "long faux locs, loose",
    "defined 3C ringlets, shoulder-length",
    "cropped natural coils, close to the head",
    "short tapered natural cut",
    "sleek pressed hair, shoulder-length",
]

# Male styles — shared across ethnicities (cuts work universally)
_CHAR_HAIR_STYLES_MALE = [
    "short cropped cut, neat",
    "short textured cut with a natural part",
    "buzz cut, close to the scalp",
    "faded sides with longer hair on top",
    "slicked back, medium length",
    "messy textured crop",
    "short curls, close-cropped",
    "tight natural curls, short",
    "short afro, rounded",
    "mid-length waves, loosely swept back",
    "short dreadlocks",
    "shoulder-length straight hair, centre-parted",
    "shaved head",
    "close-cropped with a defined hairline",
    "short tapered cut, higher on top",
    "undercut with longer hair swept to one side",
    "short neat side part",
    "textured quiff, short sides",
]

# ── Accent pool ────────────────────────────────────────────────────────────────
# Mapped per ethnicity. Only injected when dialogue is present.
# Phrased as LTX-2.3 voice description language — pace, texture, accent together.
_CHAR_ACCENTS = {
    "Japanese":         "speaks in Japanese, voice soft and precise, each word measured",
    "Korean":           "speaks in Korean, tone bright and clipped, vowels clean and forward",
    "Chinese":          "speaks in Mandarin, voice steady and level, consonants crisp",
    "East Asian":       "speaks in accented English with a soft East Asian lilt, vowels slightly flattened",
    "South Asian":      "speaks in a warm Indian accent, vowels rounded and musical, slight sing-song rhythm",
    "Indian":           "speaks in a clear Indian accent, consonants precise, cadence unhurried and melodic",
    "Southeast Asian":  "speaks in lightly accented English with a soft Southeast Asian tone, gentle and even",
    "Filipino":         "speaks in Filipino-accented English, warm and expressive, slight upward lilt at sentence ends",
    "Vietnamese":       "speaks in Vietnamese-accented English, tone rising and precise, soft consonants",
    "Middle Eastern":   "speaks in a warm Middle Eastern accent, deep vowels, unhurried and deliberate",
    "North African":    "speaks in a rich North African accent, warm and resonant, slight French influence in the rhythm",
    "Black":            "speaks with a deep resonant voice, relaxed and unhurried, warm American cadence",
    "Latina":           "speaks in accented English with a warm Latin rhythm, vowels open and expressive",
    "White":            "",  # No accent note — neutral, let LLM decide naturally
    "mixed race":       "",  # No accent note — intentionally neutral
    "Indigenous":       "speaks in a low unhurried voice, measured and grounded, each word given full weight",
    "Pacific Islander": "speaks in a warm Pacific Islander accent, slow and melodic, voice deep and relaxed",
    # Jamaican is rolled separately for Black characters with a chance roll
    "_jamaican":        "speaks in a rich Jamaican accent, rhythm lilting and musical, consonants sharp and warm",
    "_british_black":   "speaks in a London accent with Caribbean warmth, clipped and quick with soft vowels",
    "_african":         "speaks in a deep West African accent, voice rich and resonant, cadence stately and unhurried",
}


# ── Body type pools ───────────────────────────────────────────────────────────
# All entries are conventionally attractive / camera-friendly.
# Chubby, fat, heavyset, plus-size etc are deliberately excluded —
# if the user wants those they describe it themselves.
# Split by ethnicity group for plausible combinations.
# "Receding hairline" removed from male pool for same reason.

# East Asian female — petite to medium, slim dominant
_CHAR_BODY_TYPES_FEMALE_EAST_ASIAN = [
    "petite and slender, small-framed",
    "petite and slender, small-framed",
    "slim with a flat stomach and narrow hips",
    "slim with a flat stomach and narrow hips",
    "thin with delicate bone structure",
    "lean and tall with long limbs",
    "athletic build with defined shoulders",
    "lean and athletic with visible muscle definition",
    "strong legs and a narrow waist",
    "full hourglass figure with wide hips and a defined waist",
]

# White female — full range, slim to curvy, all attractive
_CHAR_BODY_TYPES_FEMALE_WHITE = [
    "slender build with narrow shoulders",
    "lean and tall with long limbs",
    "lean and tall with long limbs",
    "slim with a flat stomach and narrow hips",
    "athletic build with defined shoulders",
    "lean and athletic with visible muscle definition",
    "strong legs and a narrow waist",
    "full hourglass figure with wide hips and a defined waist",
    "full hourglass figure with wide hips and a defined waist",
    "curvy with a round bust and full hips",
    "big-busted with a narrow waist and wide hips",
    "tall and willowy with long legs",
    "statuesque, over six feet, lean",
]

# Fallback pool — only hits if an ethnicity outside the main three somehow appears
_CHAR_BODY_TYPES_FEMALE_CURVY = [
    "full hourglass figure with wide hips and a defined waist",
    "curvy with a round bust and full hips",
    "athletic build with defined shoulders",
    "lean and athletic with visible muscle definition",
    "slim with a flat stomach and narrow hips",
    "strong legs and a narrow waist",
]

# Black female — athletic and curvy, all camera-attractive
_CHAR_BODY_TYPES_FEMALE_BLACK = [
    "full hourglass figure with wide hips and a defined waist",
    "full hourglass figure with wide hips and a defined waist",
    "curvy with a round bust and full hips",
    "big-busted with a narrow waist and wide hips",
    "athletic build with defined shoulders",
    "lean and athletic with visible muscle definition",
    "strong legs and a narrow waist",
    "tall and willowy with long legs",
    "statuesque, over six feet, lean",
]

# Male — lean to muscular, all attractive, no heavyset
_CHAR_BODY_TYPES_MALE_ATTRACTIVE = [
    "lean and wiry with narrow shoulders",
    "tall and slim with long limbs",
    "slim with a flat stomach, average build",
    "compact and lightly muscled",
    "athletic build with broad shoulders and a tapered waist",
    "athletic build with broad shoulders and a tapered waist",
    "muscular and powerfully built, broad chest",
    "lean and athletic with visible muscle definition",
    "lean and athletic with visible muscle definition",
    "tall with a rangy, angular frame",
    "well-built with a defined chest and flat stomach",
    "well-built with a defined chest and flat stomach",
    "wiry and compact, all sinew, no excess",
]


def _build_char_seed(rng: random.Random, adult_only: bool = False, gender: str = "female") -> str:
    """
    Build a randomised character description with ethnicity-aware
    hair colour, hair style, and accent.
    gender: 'female' | 'male' | 'neutral' (neutral picks randomly)
    Ethnicity pools are gender-specific:
      female → mostly White / East Asian / rare Black
      male   → mostly White / some East Asian / very rare Black
    """
    age_pool        = _CHAR_AGES_ADULT if adult_only else _CHAR_AGES
    age             = rng.choice(age_pool)
    age_int         = int(age)

    if gender == "neutral":
        gender = rng.choice(["female", "male"])

    # ── Pick ethnicity from the correct gender pool ───────────────────────────
    eth_pool        = _CHAR_ETHNICITIES_MALE if gender == "male" else _CHAR_ETHNICITIES_FEMALE
    ethnicity, skin = rng.choice(eth_pool)

    # ── Hair colour — ethnicity aware ─────────────────────────────────────────
    if age_int >= 40 and rng.random() < 0.35:
        # 35% chance of grey for 40+ regardless of ethnicity
        hair_colour = rng.choice(_CHAR_HAIR_COLOURS_GREY)
    elif ethnicity in ("Japanese", "Korean", "Chinese", "East Asian"):
        hair_colour = rng.choice(_CHAR_HAIR_COLOURS_EAST_ASIAN)
    elif ethnicity == "White":
        hair_colour = rng.choice(_CHAR_HAIR_COLOURS_WHITE)
    else:
        # Black — use dark pool
        hair_colour = rng.choice(_CHAR_HAIR_COLOURS_DARK)

    # ── Hair style — ethnicity aware ──────────────────────────────────────────
    if gender == "male":
        hair_style = rng.choice(_CHAR_HAIR_STYLES_MALE)
    elif ethnicity == "Black":
        hair_style = rng.choice(_CHAR_HAIR_STYLES_TEXTURED)
    elif ethnicity in ("Japanese", "Korean", "Chinese", "East Asian", "White"):
        hair_style = rng.choice(_CHAR_HAIR_STYLES_STRAIGHT)
    else:
        # Fallback for any future additions
        hair_style = rng.choice(_CHAR_HAIR_STYLES_STRAIGHT)

    # ── Accent — ethnicity aware, injected as voice note ──────────────────────
    if ethnicity == "Black":
        accent_roll = rng.random()
        if accent_roll < 0.25:
            accent = _CHAR_ACCENTS["_jamaican"]
        elif accent_roll < 0.45:
            accent = _CHAR_ACCENTS["_british_black"]
        elif accent_roll < 0.65:
            accent = _CHAR_ACCENTS["_african"]
        else:
            accent = _CHAR_ACCENTS["Black"]
    else:
        accent = _CHAR_ACCENTS.get(ethnicity, "")

    # ── Body type — ethnicity and gender aware ────────────────────────────────
    if gender == "male":
        body_type = rng.choice(_CHAR_BODY_TYPES_MALE_ATTRACTIVE)
    elif ethnicity in ("Japanese", "Korean", "Chinese", "East Asian"):
        body_type = rng.choice(_CHAR_BODY_TYPES_FEMALE_EAST_ASIAN)
    elif ethnicity == "White":
        body_type = rng.choice(_CHAR_BODY_TYPES_FEMALE_WHITE)
    else:
        # Black
        body_type = rng.choice(_CHAR_BODY_TYPES_FEMALE_BLACK)

    # ── Assemble ──────────────────────────────────────────────────────────────
    if gender == "male":
        base = (
            f"a {age}-year-old {ethnicity} man, "
            f"{hair_colour} hair, {hair_style}, "
            f"{skin}, "
            f"{body_type}"
        )
    else:
        base = (
            f"a {age}-year-old {ethnicity} woman, "
            f"{hair_colour} hair in a {hair_style}, "
            f"{skin}, "
            f"{body_type}"
        )

    if accent:
        base += f", {accent}"

    return base


# ── Node ──────────────────────────────────────────────────────────────────────

class LTX2PromptArchitectQwen:
    """
    LTX-2.3 Easy Prompt — Huihui Qwen3.5-9B Edition

    Full LD-grade prompt engineering ported to Qwen3.5-9B-abliterated.
    All style presets, content detection, garment sequences, spatial blocking,
    dialogue control, and character seeds from the main LD node.
    Single model: huihui-ai/Huihui-Qwen3.5-9B-abliterated
    """

    # ── System prompt (full LD version) ──────────────────────────────────────
    SYSTEM_PROMPT = """You are a cinematic prompt writer for LTX-2.3, an AI video generation model. Expand the user's rough idea into a precise, director-level, video-ready prompt. Write as a single flowing paragraph in present tense. Be specific — LTX-2.3 rewards detail and rewards you for using it.

LTX-2.3 CAPABILITIES — exploit all of these:
- Detailed prompts outperform short ones, especially for longer clips. A 10-second clip needs a rich, full prompt to fill the duration.
- Fine detail renders accurately: fabric weave, individual hair strands, skin texture, surface wear, material finish. Describe these.
- Strong prompt adherence — you can direct camera AND subject motion simultaneously with precision.
- Native portrait up to 1080x1920 — compose vertically, not as a cropped landscape.
- Improved audio — voice quality, ambient sound, and sync all respond well to description. Sound is always present.
- Always include motion. Static prompts produce static video.
- Single-subject scenes give the sharpest, most faithful output. Two subjects is viable with clear blocking. Three or more risks clarity degradation — keep their actions simple, non-overlapping, and explicitly spatially separated.

SCENE INTEGRITY:
Build outward from what the user gave you — do not contradict or override it.
If the user described a location, enrich it with specific textures and atmosphere: a city street becomes "wet asphalt reflecting neon, steam rising from a grate, the cold blue cast of a streetlamp". A café becomes "warm tungsten light, fogged glass, the grain of the wooden tabletop".
If the user gave NO location, shoot in a neutral unspecified space — do not invent a warehouse, forest, or bedroom they didn't ask for.
Do NOT add: rose petals, candles, silk sheets, glitter, sparkles, or sentimental filler that isn't grounded in the scene.
Do NOT invent props or characters the user didn't mention.
Every addition must be (a) from the user's input, (b) a texture/material/atmosphere detail that enriches what they described, or (c) a necessary camera/staging decision.

CAMERA ORIENTATION — IMPORTANT:
The DEFAULT is that the subject FACES the camera. ONLY write rear view or camera-behind framing if the user explicitly said: "from behind", "rear view", "back view", "follow her from behind", "watches her from behind", "camera behind", "over her shoulder from behind". Do NOT default to rear view just because the subject is walking.

SCENE DIRECTION — build the prompt in this order:
1. Style & genre — use the STYLE INSTRUCTION as the aesthetic anchor. Where it fits, weave a film stock or camera reference into the prose naturally — e.g. "the image carries a Kodak 2383 warmth", "shot on an ARRI Alexa, clean and clinical", "Fuji Eterna desaturation softens the shadows". NEVER as a bracketed tag. It must read as part of a sentence.
2. Shot scale & framing — choose the right scale for the scene and name it in the prose. Use these terms:
   - Extreme close-up: fills the frame with a single feature — an eye, a mouth, a hand, a texture
   - Close-up: face from chin to crown, or a hand, a detail — intimate, personal
   - Medium close-up: head and shoulders, face dominant — the standard for dialogue and emotion
   - Medium shot: waist up — character and some environment in frame together
   - Medium wide / cowboy shot: thighs up — character in context, readable body language
   - Wide shot / full shot: full body, environment present and readable
   - Establishing shot: wide, environment dominant — sets the location
   - Aerial / bird's-eye: camera directly above, looking straight down
   - Low angle: camera below subject, looking up — power, dominance, scale
   - High angle: camera above subject, looking down — vulnerability, surveillance
   - Dutch angle: camera tilted on its axis — unease, tension, disorientation
   - Over-the-shoulder (OTS): camera behind one subject, looking past them at another
   - Point-of-view (POV): camera is the character's eyes
   - Two-shot: both subjects visible and balanced in frame
   - Insert shot: tight cut to a specific object or detail in the scene
   Also describe depth of field using natural language: "razor-thin depth of field", "deep focus, everything sharp front to back", "shallow depth of field with creamy background blur", "soft bokeh behind the subject".
   Match detail level to shot scale — close-ups require more granular description (pores, hair strands, fabric weave, micro expressions). Wide shots need environmental depth (foreground elements, layers of space, atmospheric haze or light).
3. Character — ALWAYS state age as a specific number: "a 27-year-old woman". Default range 18–35 unless context implies otherwise. Use 40+ only if the user said "older", "mature", "middle-aged", "elderly". Use under-18 only if the user explicitly placed them in a school, childhood, or teen context — NEVER for sexual or suggestive content. Then: hair texture and colour, skin tone, body type, clothing with fabric and material ("a fitted black cotton crop top", "worn light-wash denim jeans", "a loose cream silk blouse"). Use the exact words the user used. Include micro expressions and subtle physical tells: "the corners of her lips tighten slightly", "her eyes momentarily lose focus", "a faint crease forms between her brows".
4. Scene & environment — location, time of day, lighting quality and direction, colour temperature, surface textures ("scuffed hardwood floor", "rain-streaked glass", "warm tungsten interior"). Only what the user described. Avoid high-frequency visual patterns in clothing, backgrounds, and surfaces — they cause flickering artifacts. Favour solid colours and simple textures.
5. Spatial blocking — MANDATORY. Define left/right position, foreground/background depth, who faces what. "She stands centre-left in the foreground, facing camera. He sits well behind her at the right edge of frame, slightly out of focus." For single subjects: anchor them — "She stands centre-frame in the immediate foreground, facing camera, the background soft behind her." Block every scene like a director.

ACTION & MOTION:
6. Motion — describe all four simultaneously when possible: who moves, what moves, how they move, what the camera does. "She steps forward and turns as the camera tracks left and slowly pushes in." If the scene is genuinely static, add ONE subtle environmental motion only: a slow camera drift, wind lifting the hair, a distant background detail. Do not pile on micro-movements. For smooth motion: stable dolly, smooth tracking, constant-speed pan. Avoid chaotic or rapid movement unless the style requires it.
7. Texture in motion — how materials behave as things move: "the fabric pulls taut across her hips", "her hair lifts and separates", "the denim creases at the knee as she bends". LTX-2.3 renders this accurately.
8. Camera movement — prose verbs only, never bracketed tags. "The shot slowly pushes in" not "(Push in)". Use: dolly in/out, rack focus, whip pan, push in, crane up, handheld drift, slow orbit, creep forward, track right, gimbal arc, slow pull back, tilt up/down, pan left/right. Describe camera movement relative to the subject. After a camera move, describe how the subject appears in the new framing — this helps the model complete the motion accurately: "the camera pushes in until her face fills the frame, her eyes now the sharpest point in the composition".

SOUND — always present, always described:
9. Sound is MANDATORY — there are no silent scenes. Weave it as descriptive prose. Max 2 sounds per beat. When action and sound sync, say so explicitly: "her footsteps land on each downbeat", "the shutter clicks precisely as her fingers press". Sync language strengthens audio-visual coherence.
- Every sound needs sensory detail. Not "footsteps" — "the sharp rhythmic clack of heels on cold marble, each step ringing with a hollow echo." Not "rain" — "rain hitting the glass in irregular bursts, a low persistent hiss beneath it."
- Speaking characters: always describe voice quality — pace, texture, register. "Her voice barely above a breath", "a low gravelly rumble", "fast and clipped, each word landing hard", "slow and deliberate, each syllable weighted".
- Music/performance scenes: describe the track as physical sensation — "a deep kick drum punches through the floor, the bass felt in the chest", "sharp hi-hats over a slow rolling groove". Do NOT reduce it to "music plays".
- Never use [AMBIENT: ...] tags. No abstract emotional audio — no "tension fills the air".

CRITICAL RULES:
- NEVER write scene endings. Prompts describe ongoing action, not conclusions. Forbidden: "the scene ends", "fades to black", "the camera cuts", "comes to a close". Also forbidden: winding-down summary sentences — "In this quiet moment...", "leaving only the warmth of...", "ending on the soft...". The prompt is always mid-action.
- NEVER invent characters. If the user described one person, there is one person. No bystanders, passers-by, or observers unless the user wrote them.
- NEVER use internal emotional labels — not "she is sad", "he feels confused", "she looks happy". Describe only what is physically visible: "the corners of her mouth pull down", "his eyes lose focus for a moment", "a faint crease forms between her brows".
- AVOID conflicting lighting logic. Do not mix a candlelit interior with harsh midday sunlight unless the scene calls for it. Mixed light sources that contradict each other confuse the model.
- AVOID chaotic or complex physics — multiple objects colliding unpredictably, crowds in chaotic motion, or rapid overlapping movements introduce artifacts. Choreographed or rhythmic movement (dancing, sport, deliberate action) is fine. Random physical chaos is not.
- TEXT AND LOGOS: readable text on signs, labels, or screens is unreliable. Do not ask for legible text in the frame.

DIALOGUE — follow the DIALOGUE INSTRUCTION exactly. Use LTX-2.3's structured dialogue format: break speech into short phrases with acting directions between each line. Do NOT write long dialogue in one block. Invented dialogue MUST be grounded in what is visibly happening in the scene — do NOT invent backstory, history, relationships, or context not present in the user's input. A boxer training alone may grunt a short exertion sound; she may not deliver lines about her past.
- Write a short spoken phrase in quotes
- Follow with a physical acting direction: "he pauses, glancing left", "her jaw tightens", "she exhales slowly"
- Then the next phrase, then the next direction
Example: "I remember after you came along..." He pauses, looking to the side. "Your mother..." His eyes widen slightly. "Said something I never quite understood," his voice dropping to almost nothing.
No [DIALOGUE: ...] tags. No stage directions in brackets. If the character speaks a specific language or has an accent, state it: "speaks in Japanese", "with a thick Southern drawl", "in accented English".
VOICE QUALITY — always describe HOW a character's voice sounds when they speak: pace, texture, register. "her voice barely above a breath", "a low gravelly rumble", "fast and clipped, each word landing hard", "slow and deliberate, each syllable weighted". Voice quality is as important as the words themselves.

UNDRESSING — when clothing removal is stated or clearly implied:
Write a dedicated undressing segment BEFORE any nudity. Name every garment. Describe each removal step by step. Describe what skin is revealed and how the fabric behaves. Never jump from clothed to naked.

GARMENT SEQUENCES — use the correct physical order for each type:
- T-shirt / shirt / crop top (full removal): grip the hem at the waist → pull fabric up past the stomach → past the ribs → over the chest → over the head → off the arms → dropped
- T-shirt / shirt / crop top (lift only, not removed): grip the hem → slowly gather and lift → rises past the stomach → past the navel → past the ribs → chest comes into full view → held there. One sentence per step.
- Dress (pullover): grip hem at thighs → lift past hips → past waist → gathered up over chest → over the head → falls
- Dress (zip back): hand reaches behind → finds the zip → pulls it slowly down → fabric loosens and parts → slipped off shoulders → slides down the body → pools at the floor
- Blouse / button-down: each button worked top to bottom one at a time → fabric parts → shrugged off shoulders → slides down arms → dropped
- Bra: hand behind to clasp → unhooked → straps eased off each shoulder → cups fall away
- Jeans / trousers: button popped → zip down → pushed over hips → down the thighs → stepped out of
- Underwear / knickers / thong: thumbs hooked into waistband → pushed down → stepped out of

NO INVENTED RESOLUTION: If the shirt goes up, it stays up. Do NOT write her covering herself, lowering it, or reversing the action unless the user asked for it.

PORTRAIT MODE — 9:16 vertical: frame vertically from the start. Tight head-to-torso shots. Vertical action and camera movement. No wide horizontal compositions.

WRITING RULES:
- Present tense throughout
- Specific over vague: "a loose grey cotton t-shirt, collar slightly stretched" beats "a shirt"
- Concrete over poetic: "her dress falls to the floor" beats "the fabric cascades"
- No filler adjectives: not "beautiful", "stunning", "gorgeous" — describe what's visible
- Always include motion. Always include sound. Both are mandatory.
- Always include natural motion blur — keep movement fluid, never frozen or strobed.
- Avoid high frequency patterns in clothing, backgrounds, and surfaces — these cause flickering.
- Flowing prose, not lists
- MINOR CHARACTERS (under 18): describe face expression, hair, and clothing appearance only. Do NOT write fabric-body-contact descriptions — no 'fabric pulls taut', 'presses against', 'clings to' or any clothing-on-skin language. Keep all physical description age-appropriate and non-body-focused.

OUTPUT RULES:
Output ONLY the prompt. No preamble, no "Sure!", no "Here's your prompt:", no compliance notes, no word counts, no brackets after the final sentence. Begin immediately with the shot or style description. End with the last sentence of the scene."""

    # ── Style presets (full LD set) ───────────────────────────────────────────
    STYLE_PRESETS = {
        "None — let the LLM decide": ("", False),
        "Cinematic — Drama": (
            "STYLE: Cinematic drama. Intimate, character-driven. Shallow depth of field — subject sharp, "
            "world behind them soft. Colour grade: cool shadows, warm skin tones, restrained palette. "
            "Camera: medium close-ups and close-ups dominate. Moves are slow and purposeful — "
            "a slow push-in on a face, a rack focus between two people, a static hold that lets the actor breathe. "
            "Lighting: motivated practical sources — a lamp, a window, a candle. Never flat. "
            "Kodak 2383 print emulation. Sound: intimate and close — breath, fabric, small environmental detail. "
            "No wide establishing shots unless the user asked for them. Stay with the character.", False),
        "Cinematic — Epic": (
            "STYLE: Epic cinematic. Scale and environment are the protagonist. "
            "Wide establishing shots and vast compositions that make people feel small against the world. "
            "Camera: sweeping crane moves, slow orbital shots, long tracking shots across terrain. "
            "Colour grade: rich, contrasty — deep shadows, luminous highlights. "
            "Kodak 5219 for natural daylight scenes, ARRI Alexa for clean digital grandeur. "
            "Sound: environmental and large — wind, distance, the weight of open space. "
            "Every frame should feel like a poster. Build depth with foreground elements. "
            "Natural motion blur on all movement.", False),
        "Cinematic — Intimate close-up": (
            "STYLE: Intimate close-up cinema. The entire world is a face, a hand, a detail. "
            "Razor-thin depth of field — one eye sharp, the other already soft. Bokeh is smooth and organic. "
            "Framing: extreme close-ups and close-ups only — fill the frame with a face, a hand, a single feature. "
            "Camera: barely moves — micro drifts and imperceptible breathing movement. "
            "Colour grade: skin-tone faithful, no heavy colour casts. Warm and close. "
            "Lighting: one soft source, one fill, nothing else. "
            "Sound: amplified intimacy — breath, the swallow of saliva, fabric against skin, heartbeat proximity. "
            "Reveal character through detail — a tightening jaw, a flicker of the eye, fingers finding each other. "
            "This is portraiture as cinema.", False),
        "Slow-burn thriller": (
            "STYLE: Slow-burn psychological thriller. Tight framing, long held shots, shallow depth of field. "
            "Colour palette: desaturated teal and amber. Sound design is sparse — silence punctuated by single sounds. "
            "Camera moves deliberately and slowly. Tension built through restraint, not action.", False),
        "Handheld documentary": (
            "STYLE: Handheld documentary. Camera moves with the subject, never static. Slight shake on movement. "
            "Natural available light only — no studio lighting. Colour grade: flat, slightly washed. "
            "Intimate and observational — camera follows, never leads.", False),
        "High fashion editorial": (
            "STYLE: High fashion editorial. Striking, composed frames. Hard directional lighting with deep shadows. "
            "Colour palette: high contrast, often monochrome or single accent colour. "
            "Movement is deliberate and posed — model-aware. Camera movements are slow and precise. "
            "ENVIRONMENT NOTE: Do not invent luxury props, chandeliers, marble, or opulent settings "
            "unless the user described them. Apply the editorial aesthetic to whatever location the user specified.", False),
        "Noir — deep shadows, venetian light": (
            "STYLE: Classic noir. Low-key lighting, venetian blind shadow patterns across faces and walls. "
            "Black and white or heavily desaturated with single colour accent. "
            "Camera angles: low, Dutch tilt, shot through objects. Mood is foreboding and fatalistic.", False),
        "Golden hour drama": (
            "STYLE: Golden hour drama. Warm amber and orange light from a low sun. Heavy lens flare. "
            "Soft shadows, glowing skin tones. Wide establishing shots and medium shots. Emotional, sweeping camera movement. "
            "Colour grade: warm, slightly overexposed highlights.", False),
        "Horror — desaturated, harsh contrast": (
            "STYLE: Horror. Heavily desaturated colour, crushed blacks. Harsh top-down or under-lighting. "
            "Camera movements are slow and uneasy — never reassuring. "
            "Framing leaves negative space — empty doorways, dark corners. No warmth in the image.", False),
        "Erotic cinema — tasteful, cinematic": (
            "STYLE: Tasteful erotic cinema. Warm, intimate lighting — practical sources only. "
            "Shallow depth of field. Camera moves slowly and deliberately. "
            "Colour grade: warm skin tones, soft highlights. "
            "Sensual but not pornographic — implication over explicit detail. Slow, breathing pace. "
            "SCOPE NOTE: This style sets the aesthetic and mood only. "
            "It does NOT grant permission to add nudity, undressing, or intimate acts beyond what the user described. "
            "Describe only what was asked for — the style wraps it, it does not expand it.", False),
        "Explicit — direct, anatomical": (
            "STYLE: Explicit adult content. Direct lighting — bodies clearly lit with no flattering shadow. "
            "Camera is close and functional — shows exactly what is happening without cinematic softening. "
            "No romantic framing. Blunt and specific. Anatomical language used directly. "
            "IMPORTANT: This style affects aesthetic and language only — it does NOT expand the scope of the scene beyond what the user asked for. "
            "Describe only what the user requested. Do not add acts, exposure, or nudity the user did not write.", False),
        "Voyeur — handheld, observational": (
            "STYLE: Voyeuristic. The camera is a person — someone who found this moment and is trying not to be noticed. "
            "CAMERA BEHAVIOUR — MANDATORY: "
            "Unless the user explicitly said 'static', the camera is ALWAYS in motion. "
            "It bobs and drifts with the natural sway of someone walking or standing. "
            "The motion is involuntary — slight vertical bounce, gentle lateral drift, micro-rotations. "
            "The camera NEVER repositions to get a better angle. It stays at the height and position of the person holding it — "
            "hip height if they are trying to be discreet, chest height if partially hidden, never raised to eye level for a clean shot. "
            "FORBIDDEN camera moves: crane up, dolly in, rack focus, orbit, push in, pull back, pan to follow. "
            "ALLOWED camera behaviour: drifts, bobs, tilts slightly as the subject moves, briefly obscured by a passing person or shelf, "
            "loses the subject for a frame and finds them again. "
            "The framing is imperfect — the subject may be partially cut off, slightly out of focus at the edges, "
            "or briefly blocked. This is what makes it feel real. "
            "Natural available light only — no fill, no flash, no colour grading. "
            "The subject is unaware. The camera does not announce itself. "
            "CRITICAL: The subject's actions are exactly as the user described — do not invent, reverse, or reframe them. "
            "If the user said she is getting dressed, she is getting dressed. If the user said she is undressing, she is undressing. "
            "The camera observes what is happening — it does not change what is happening.", False),
        "Softcore editorial — lingerie-adjacent": (
            "STYLE: Softcore editorial. Fashion-magazine aesthetic. Clean, even lighting. "
            "Colour grade: warm neutrals and soft pastels. "
            "Camera is composed — lingerie-level sensuality, no explicit content. Movement is slow and posed. "
            "SCOPE NOTE: This style sets the aesthetic only. "
            "Do NOT add undressing, nudity, or intimate acts the user did not ask for. "
            "If the user described someone sitting or standing clothed, they stay clothed. "
            "The style applies to framing and mood — not to what happens in the scene.", False),
        "Gravure Idol — Japanese glamour": (
            "STYLE: Japanese gravure idol photoshoot / glamour video. "
            "Bright, glossy, commercial magazine aesthetic. "
            "High-key natural daylight or clean studio lighting with strong rim light and soft reflector fill. "
            "CHARACTER: Unless the user has described a specific person, the subject is always an Asian woman — "
            "Japanese, Korean, or Chinese — aged 18–25, with smooth fair-to-medium skin, dark hair, and a petite to medium build. "
            "This is the authentic visual identity of the gravure genre. Do not substitute other ethnicities unless the user explicitly asked. "
            "Vivid yet smooth skin tones, slightly increased saturation, polished and flattering look. "
            "OUTFIT: If the user has not described clothing, choose ONE outfit from this varied pool — do NOT default to one-piece swimsuits every time. "
            "Rotate across: a fitted white string bikini with thin side ties; a pastel two-piece with a bandeau top and high-waist bottoms; "
            "a sheer white oversized shirt worn open over a bralette and shorts; a soft satin slip dress in ivory or blush, thigh-length; "
            "a cropped white ribbed tank top with matching low-rise shorts; a lace-trim bralette with high-waist bikini bottoms; "
            "a fitted halter-neck bikini top with sarong wrap; a light cotton button-down shirt tied at the waist over a bikini bottom; "
            "a delicate floral-print two-piece bikini; a semi-sheer mesh cover-up over a simple bikini; "
            "a soft knit crop top with micro shorts; a spaghetti-strap camisole tucked into high-waist satin shorts. "
            "Always describe the fabric — smooth, form-fitting, slightly sheer, or soft where appropriate. Pick something different each time. "
            "SETTING: If the user has not described a location, default to genre-typical environments: "
            "poolside in bright natural sunlight, a clean white studio backdrop, an outdoor garden or beach, "
            "or a bright hotel room with large windows and natural light flooding in. "
            "Posing is intentional, playful and seductive: arched back, raised or angled legs, "
            "reclining / prone / side-lying positions, teasing eye contact or glances over the shoulder, "
            "hands subtly framing or accentuating curves and outfit lines. "
            "Framing emphasises body contours — medium shots and medium close-ups highlighting bust, waist, hips and legs. "
            "Shallow depth of field with flattering background blur. "
            "CAMERA MOVEMENT: slow body pan from feet to face or face to feet, lingering holds on bust, waist and hips, "
            "gentle 360 orbit around the subject, slow tilt following a pose change, "
            "push in to a medium close-up as the subject makes eye contact with the camera. "
            "Mood is cute-provocative: youthful charm combined with clear fan-service energy. "
            "SOUND: light and intimate — soft breathing, gentle fabric rustle against skin, small giggles or sighs, "
            "subtle environmental ambience (pool water, light breeze, beach waves if outdoors). "
            "VOICE AND LANGUAGE: If dialogue is enabled — she speaks ONLY in her native language: Japanese if the character is Japanese, Korean if Korean, Mandarin if Chinese. Do NOT substitute English. If dialogue is disabled, no spoken words — use breath sounds, fabric sounds, and environmental ambience only. "
            "Voice quality is ALWAYS gentle and intimate. Choose from: a soft soothing whisper, slow sultry breath barely above silence, lullaby-soft and melodic, slow and sensual with long vowels, breathy and unhurried. Never loud, never sharp, never dramatic or urgent. "
            "DIALOGUE FORMAT — CRITICAL: When writing spoken dialogue in Japanese, Korean, or Mandarin, write the native script characters inline in the prose — do NOT put romanisation in brackets or parentheses next to the dialogue. "
            "Instead, weave the romanisation naturally into the delivery description. "
            "CORRECT: She whispers 「もっと近くで見て」, the syllables soft and drawn out, barely above breath. "
            "WRONG: She whispers 「もっと近くで見て」(Motto chikaku de mite). "
            "The parenthetical romanisation will appear as on-screen text in the video — never use it. "
            "Dialogue is minimal — one to three short phrases maximum. No dramatic monologue. No heavy music unless the user explicitly asks. "
            "SCOPE NOTE: This style sets aesthetic, posing, and framing only. "
            "Do NOT add nudity, explicit acts, or content the user did not describe.", False),
        "Amateur — naturalistic, raw": (
            "STYLE: Amateur home video aesthetic. Slightly overexposed. Natural indoor lighting — lamps, overhead. "
            "Camera is handheld and slightly uncertain. No cinematic framing. "
            "Colour: ungraded, as-shot. The imperfection is intentional.", False),
        "Action blockbuster": (
            "STYLE: Action blockbuster. Fast kinetic energy. Dutch angles, crash zooms, whip pans. "
            "Colour grade: teal and orange, high contrast. "
            "Camera is never still — it moves with every impact. Slow motion inserts on key moments.", False),
        "Sports documentary": (
            "STYLE: Sports documentary. Tracking shots following the athlete. Telephoto compression. "
            "Slow motion bursts at peak moments. Natural sound — crowd noise, impact, breathing. "
            "Colour grade: clean and neutral. Camera is athletic — it moves like it is competing too.", False),
        "Music video — stylised": (
            "STYLE: Music video. Rhythm-cut visual language — movement is driven by the beat. "
            "High contrast colour grade with stylised palette. "
            "Mix of tight close-ups and dramatic wide shots. Camera movement is expressive, not documentary. "
            "AUDIO: Music is present — describe the track's energy, tempo, and texture as physical sound: "
            "'a driving four-on-the-floor kick', 'sharp hi-hats', 'a warm bass line pulsing beneath the mix'. "
            "Sync camera and body movement to the implied beat. "
            "IMPORTANT: This style describes HOW the scene is shot — not what is in it. "
            "All people, subjects, and actions described by the user must still appear in the scene. "
            "Do not replace the user's scene with abstract environment shots or B-roll. "
            "Film the scene the user described, through a music video camera.", False),
        "Lo-fi home video — VHS": (
            "STYLE: Lo-fi home video. VHS tape aesthetic — slightly washed colour, faint scan lines, soft edges. "
            "Colour grade: faded, slightly green-shifted. Camera is handheld and casual. "
            "Intimate domestic setting implied. Imperfection is the aesthetic. "
            "IMPORTANT: This style describes HOW the scene is shot — not what is in it. "
            "All people, subjects, and actions described by the user must still appear in the scene. "
            "Do not replace the user's scene with an empty room, leftover objects, or nostalgic cutaways. "
            "Film the scene the user described, through a VHS camera.", False),
        "Hyper-real 4K — clinical sharpness": (
            "STYLE: Hyper-real 4K. Clinical sharpness — every texture, pore, and fibre rendered in full detail. "
            "Even lighting, no blown highlights, no crushed blacks. "
            "Camera movement is minimal and precise. The image is almost uncomfortably detailed.", False),
        "Dreamy — soft focus, slow motion": (
            "STYLE: Dreamy aesthetic. Soft focus edges with sharp centre. Pastel colour bleed. "
            "Movement is slow — the frame breathes rather than cuts. "
            "Shallow depth of field with heavy bokeh. Light sources bloom and halo.", False),
        "Gritty realism — flat, natural light": (
            "STYLE: Gritty realism. Flat colour grade, no cinematic enhancement. Natural light only — "
            "whatever is available in the location. Camera is direct and unsentimental. "
            "No stylisation. The scene is shot as if it is actually happening.", False),
        "POV — first person, immersive": (
            "STYLE: First-person POV. The camera IS the viewer's eyes. "
            "Frame moves as a head would — natural breathing movement, slight tilt on turns. "
            "Everything is seen, not watched. Close physical detail — hands, surfaces, faces at speaking distance.", False),
        "Portrait vertical — 9:16 mobile": (
            "STYLE: Native portrait video, 9:16 aspect ratio. Optimised for mobile — TikTok, Reels, Shorts. "
            "Frame is vertical throughout. Tight head-to-torso framing. "
            "Action moves vertically in frame. Camera stays close. No wide horizontal composition.", True),
        "Selfie — self-shot, arm's length": (
            "STYLE: Self-shot selfie video. The subject is holding the camera themselves — "
            "outstretched arm, camera facing back at them, roughly 50–70cm from their face. "
            "9:16 vertical frame throughout. "
            "FRAMING: tight head-and-shoulders. The subject's face and upper chest fill most of the frame. "
            "The background is whatever is physically behind them — visible and readable, not blurred out. "
            "Moderate depth of field — subject sharp, background softly out of focus but present. "
            "CAMERA BEHAVIOUR — MANDATORY: the camera is an extension of the subject's arm. "
            "It moves when they move — bobs as they walk, tilts when they turn their head, "
            "dips when they look down, swings slightly when they gesture. "
            "The subject controls the framing — they pull back to show more context, "
            "push forward when they want to fill the frame with their face. "
            "This is self-directed. The subject is fully aware of the camera and performing to it. "
            "FORBIDDEN: tripod stillness, gimbal smoothness, rack focus, dolly, crane, orbit. "
            "The camera never separates from the subject's hand or floats independently. "
            "COLOUR: clean and bright, natural available light, no cinematic grade. "
            "SOUND: the subject's voice is close and direct — microphone is right at the camera. "
            "Voice is dominant. Ambient environment sits underneath at lower level. "
            "SCOPE NOTE: This style sets the shooting aesthetic only — "
            "it does NOT add content, nudity, or actions the user did not describe.", True),
        "Anime — Japanese animation": (
            "STYLE: Japanese anime. Hand-drawn animation aesthetic — clean ink outlines, flat colour fills with "
            "subtle cel shading. Large expressive eyes, stylised facial features. "
            "Colour palette: vivid, high saturation with strong accent colours. "
            "Motion: fluid on key poses, held on reaction shots — classic anime timing with smear frames on fast movement. "
            "Background art is painterly and detailed behind simpler foreground characters. "
            "Camera: dynamic angles, speed lines on action, slow drift on emotional beats. "
            "Render every subject — human, animal, object — in this style regardless of what was described.", False),
        "2D cartoon — hand-drawn": (
            "STYLE: Classic hand-drawn 2D cartoon. Expressive ink outlines with variable line weight — thick on silhouette, thin on interior detail. "
            "Flat colour fills, minimal shading, bold colour palette. "
            "Movement uses squash-and-stretch — characters exaggerate physics for comedic or emotive effect. "
            "Timing is snappy — fast actions are faster than real life, held poses linger longer. "
            "Background art is simplified and stylised, never photorealistic. "
            "Camera: mostly static or slow panning, occasional dramatic zoom. "
            "Render every subject in this style regardless of what was described.", False),
        "3D CGI — Pixar/DreamWorks": (
            "STYLE: High-end 3D CGI animation in the style of Pixar or DreamWorks. "
            "Subsurface scattering on skin and organic surfaces — warmth and translucency visible in light. "
            "Highly detailed surface textures: pores, fur, feathers, fabric weave all rendered at full resolution. "
            "Expressive faces with large eyes capable of subtle micro-expressions. "
            "Warm, soft three-point lighting with dappled environmental light and gentle shadows. "
            "Camera: smooth cinematic moves — slow push-ins, gentle orbits, rack focus between characters. "
            "Colour grade: warm, slightly saturated, storybook palette. "
            "Render every subject in this style regardless of what was described.", False),
        "Stop motion — claymation": (
            "STYLE: Stop motion claymation. Physical clay or puppet aesthetic — visible fingerprints and tool marks in surfaces, "
            "slight imperfections in every frame that reveal the handmade origin. "
            "Movement is slightly jerky and deliberate — 12 frames per second gives it weight and tactility. "
            "Textures: matte, tactile, slightly waxy. Colours are saturated but not digital. "
            "Sets are physical miniatures — tangible depth, real shadows from practical lights. "
            "Camera: locked off or on simple mechanical rigs — no digital smoothing. "
            "Render every subject in this style regardless of what was described.", False),
        "Comic book / graphic novel": (
            "STYLE: Comic book or graphic novel. Bold ink outlines, halftone dot patterns in shadow areas. "
            "Colour is flat with hard-edged shadows — no soft gradients. "
            "Panel energy: dynamic Dutch angles, strong perspective distortion on action, tight close-ups on emotion. "
            "Speed lines radiate from points of impact or fast movement. "
            "Colour palette: high contrast, often limited to 3-5 colours per scene with heavy black ink. "
            "Camera moves like a comic panel transition — hard cuts between angles, no smooth motion blur. "
            "Render every subject in this style regardless of what was described.", False),
        "Cel-shaded — flat colour 3D": (
            "STYLE: Cel-shaded 3D. Three-dimensional geometry rendered with flat, stepped colour fills — no soft gradients. "
            "Hard shadow threshold: shadow areas are a single flat darker tone, lit areas a single flat lighter tone. "
            "Ink outlines on all silhouettes and major edges. "
            "The image reads as animated despite being 3D — the shading removes photorealism entirely. "
            "Colour palette: clean, bold, graphic. "
            "Camera: precise and composed — treats 3D space like a 2D stage. "
            "Render every subject in this style regardless of what was described.", False),
        "Rotoscope — animated over live action": (
            "STYLE: Rotoscoped animation. The movement is real — traced from live action footage — "
            "giving it uncanny physical accuracy within a hand-drawn or painted surface. "
            "Outlines are hand-drawn over every frame: slightly wobbly, varying in weight, never perfectly clean. "
            "Colour is either painted in loose washes or held as flat fills inside the traced lines. "
            "The result feels simultaneously real and unreal — human movement with an illustrated skin. "
            "Background may be live action or painted. Camera movement follows the original footage exactly. "
            "Render every subject in this style regardless of what was described.", False),
        "Cyberpunk neon illustrated": (
            "STYLE: Cyberpunk illustrated. Neon-lit urban environment — magenta, cyan, electric blue, acid green. "
            "Hard rim lighting from neon signs carves subjects out of near-total darkness. "
            "Rain-slick surfaces reflect light in pools and streaks. "
            "The aesthetic blends hyper-detailed digital illustration with cinematic composition — "
            "not photorealistic, but not flat cartoon either. Think graphic novel meets blade runner. "
            "Typography and UI elements float in the environment as holographic overlays. "
            "Camera: low angles, wide lenses, dramatic fog and haze. "
            "Render every subject in this style regardless of what was described.", False),
        "Sci-fi — cinematic, practical": (
            "STYLE: Cinematic science fiction. Clean, practical-feeling environments — metal corridors, "
            "reinforced glass, industrial lighting rigs. Colour palette: cool blue-white with accent LEDs, "
            "deep shadow with hard point sources. No fantasy or magic — everything looks functional and built. "
            "Camera: wide establishing shots to sell the scale of the environment, then close on faces or hands "
            "for intimacy. Lens flare on light sources. Sound is mechanical — hum of systems, "
            "footsteps on metal grating, distant machinery. "
            "Render every subject in this style regardless of what was described.", False),
    }

    PRESET_FPS = {
        "None — let the LLM decide":                24,
        "Cinematic — Drama":                        24,
        "Cinematic — Epic":                         24,
        "Cinematic — Intimate close-up":            24,
        "Slow-burn thriller":                       24,
        "Handheld documentary":                     30,
        "High fashion editorial":                   24,
        "Noir — deep shadows, venetian light":      24,
        "Golden hour drama":                        24,
        "Horror — desaturated, harsh contrast":     24,
        "Erotic cinema — tasteful, cinematic":      24,
        "Explicit — direct, anatomical":            30,
        "Voyeur — handheld, observational":         30,
        "Softcore editorial — lingerie-adjacent":   24,
        "Gravure Idol — Japanese glamour":             30,
        "Amateur — naturalistic, raw":              30,
        "Action blockbuster":                       30,
        "Sports documentary":                       30,
        "Music video — stylised":                   30,
        "Lo-fi home video — VHS":                   24,
        "Hyper-real 4K — clinical sharpness":       30,
        "Dreamy — soft focus, slow motion":         24,
        "Gritty realism — flat, natural light":     30,
        "POV — first person, immersive":            30,
        "Portrait vertical — 9:16 mobile":          30,
        "Selfie — self-shot, arm's length":         30,
        "Anime — Japanese animation":               24,
        "2D cartoon — hand-drawn":                  24,
        "3D CGI — Pixar/DreamWorks":                24,
        "Stop motion — claymation":                 24,
        "Comic book / graphic novel":               24,
        "Cel-shaded — flat colour 3D":              24,
        "Rotoscope — animated over live action":    24,
        "Cyberpunk neon illustrated":               30,
        "Sci-fi — cinematic, practical":            24,
    }

    PRESET_STYLE_LABEL = {
        "None — let the LLM decide":                "",
        "Cinematic — Drama":                        "Cinematic drama, shallow depth of field, Kodak 2383.",
        "Cinematic — Epic":                         "Cinematic epic, vast wide-angle compositions.",
        "Cinematic — Intimate close-up":            "Intimate close-up cinema, razor-thin depth of field.",
        "Slow-burn thriller":                       "Slow-burn psychological thriller.",
        "Handheld documentary":                     "Handheld documentary footage.",
        "High fashion editorial":                   "High fashion editorial video.",
        "Noir — deep shadows, venetian light":      "Classic noir, black and white, venetian blind shadows.",
        "Golden hour drama":                        "Golden hour cinematic drama.",
        "Horror — desaturated, harsh contrast":     "Horror film, desaturated, harsh contrast.",
        "Erotic cinema — tasteful, cinematic":      "Tasteful erotic cinema, warm intimate lighting.",
        "Explicit — direct, anatomical":            "Explicit adult video, direct lighting.",
        "Voyeur — handheld, observational":         "Voyeuristic handheld footage.",
        "Softcore editorial — lingerie-adjacent":   "Softcore editorial, fashion magazine aesthetic.",
        "Gravure Idol — Japanese glamour":             "Japanese gravure idol, bright glossy glamour.",
        "Amateur — naturalistic, raw":              "Amateur home video, naturalistic.",
        "Action blockbuster":                       "Action blockbuster, teal and orange grade.",
        "Sports documentary":                       "Sports documentary footage.",
        "Music video — stylised":                   "Stylised music video.",
        "Lo-fi home video — VHS":                   "Lo-fi VHS home video footage.",
        "Hyper-real 4K — clinical sharpness":       "Hyper-real 4K, clinical sharpness.",
        "Dreamy — soft focus, slow motion":         "Dreamy soft focus, slow motion.",
        "Gritty realism — flat, natural light":     "Gritty realism, flat natural light.",
        "POV — first person, immersive":            "First-person POV footage.",
        "Portrait vertical — 9:16 mobile":          "Vertical 9:16 mobile video.",
        "Selfie — self-shot, arm's length":         "Selfie video, self-shot at arm's length, vertical 9:16.",
        "Anime — Japanese animation":               "Japanese anime animation, hand-drawn cel style.",
        "2D cartoon — hand-drawn":                  "2D hand-drawn cartoon animation.",
        "3D CGI — Pixar/DreamWorks":                "3D CGI animation, Pixar style.",
        "Stop motion — claymation":                 "Stop motion claymation animation.",
        "Comic book / graphic novel":               "Comic book graphic novel style.",
        "Cel-shaded — flat colour 3D":              "Cel-shaded 3D animation, flat colour fills.",
        "Rotoscope — animated over live action":    "Rotoscoped animation over live action.",
        "Cyberpunk neon illustrated":               "Cyberpunk neon illustrated, magenta and cyan.",
        "Sci-fi — cinematic, practical":            "Cinematic science fiction, practical sets.",
    }

    # ── Per-preset camera defaults ─────────────────────────────────────────────
    # (shot_angle, camera_movement) — both can be None meaning "LLM decides".
    # User widget selections override these when not set to "None — LLM decides".
    PRESET_CAMERA_DEFAULTS = {
        "None — let the LLM decide":               (None,                              None),
        "Cinematic — Drama":                       ("OTS — over the shoulder",         "Slow push in"),
        "Cinematic — Epic":                        ("Low angle — powerful, imposing",  "Pull back — reveal"),
        "Cinematic — Intimate close-up":           ("Eye-level — neutral, natural",    "Slow push in"),
        "Slow-burn thriller":                      ("High angle — vulnerable",         "Static — locked off"),
        "Handheld documentary":                    ("Eye-level — neutral, natural",    "Handheld — natural shake"),
        "High fashion editorial":                  ("Low angle — powerful, imposing",  "Static — locked off"),
        "Noir — deep shadows, venetian light":     ("Low angle — powerful, imposing",  "Slow push in"),
        "Golden hour drama":                       ("Low angle — powerful, imposing",  "Slow push in"),
        "Horror — desaturated, harsh contrast":    ("High angle — vulnerable",         "Static — locked off"),
        "Erotic cinema — tasteful, cinematic":     ("Low angle — powerful, imposing",  "Slow push in"),
        "Explicit — direct, anatomical":           ("Low angle — powerful, imposing",  "Tracking — follows subject"),
        "Voyeur — handheld, observational":        ("Low angle — powerful, imposing",  "Handheld — natural shake"),
        "Softcore editorial — lingerie-adjacent":  ("Low angle — powerful, imposing",  "Slow push in"),
        "Gravure Idol — Japanese glamour":         ("Low angle — powerful, imposing",  "Tilt up — bottom to top"),
        "Amateur — naturalistic, raw":             ("Eye-level — neutral, natural",    "Handheld — natural shake"),
        "Action blockbuster":                      ("Low angle — powerful, imposing",  "Tracking — follows subject"),
        "Sports documentary":                      ("Low angle — powerful, imposing",  "Tracking — follows subject"),
        "Music video — stylised":                  ("Eye-level — neutral, natural",    "Orbit — 360 around subject"),
        "Lo-fi home video — VHS":                  ("Eye-level — neutral, natural",    "Handheld — natural shake"),
        "Hyper-real 4K — clinical sharpness":      ("Eye-level — neutral, natural",    "Slow push in"),
        "Dreamy — soft focus, slow motion":        ("Eye-level — neutral, natural",    "Slow push in"),
        "Gritty realism — flat, natural light":    ("Eye-level — neutral, natural",    "Handheld — natural shake"),
        "POV — first person, immersive":           ("POV — first person",              None),
        "Portrait vertical — 9:16 mobile":        ("Eye-level — neutral, natural",    "Slow push in"),
        "Selfie — self-shot, arm's length":        ("High angle — vulnerable",         "Handheld — natural shake"),
        "Anime — Japanese animation":              ("Eye-level — neutral, natural",    "Tracking — follows subject"),
        "2D cartoon — hand-drawn":                 ("Eye-level — neutral, natural",    "Static — locked off"),
        "3D CGI — Pixar/DreamWorks":              ("Low angle — powerful, imposing",  "Orbit — 360 around subject"),
        "Stop motion — claymation":               ("Eye-level — neutral, natural",    "Static — locked off"),
        "Comic book / graphic novel":              ("Dutch angle — tilted, unsettling","Static — locked off"),
        "Cel-shaded — flat colour 3D":             ("Eye-level — neutral, natural",    "Orbit — 360 around subject"),
        "Rotoscope — animated over live action":   ("Eye-level — neutral, natural",    "Tracking — follows subject"),
        "Cyberpunk neon illustrated":              ("Low angle — powerful, imposing",  "Tracking — follows subject"),
        "Sci-fi — cinematic, practical":           ("Low angle — powerful, imposing",  "Slow push in"),
    }

    # ── Single model ──────────────────────────────────────────────────────────
    MODEL_HF_ID = "huihui-ai/Huihui-Qwen3.5-9B-abliterated"

    # ── Content-detection regexes — compiled once at class load ───────────────
    _EXPLICIT_RE = re.compile(
        r"\b(pussy|cock|dick|penis|vagina|clit|clitoris|anus|asshole|"
        r"tits|cum|orgasm|fuck|fucking|blowjob|handjob|penetrat\w*|"
        r"thrust\w*)\b",
        re.IGNORECASE,
    )
    _UNDRESS_CORE = (
        r"undress\w*|strip\w*|takes?\s+off|took\s+off|"
        r"removes?\w*\s+(her|his|their|the)?\s*\w*\s*"
        r"(shirt|dress|top|bra|pants|jeans|clothes|clothing|outfit|underwear|skirt|jacket|coat|robe)|"
        r"disrobe\w*|unbutton\w*|unzip\w*|peels?\s+off|pulls?\s+off|"
        r"shed\w*\s+(her|his|their)?\s*(clothes|clothing|shirt|dress)|"
        r"lift\w*\s+(her|his|their|the)?\s*(shirt|top|dress|skirt|crop|tee|t-shirt)|"
        r"(shirt|top|dress|skirt|crop|tee|t-shirt)\s+(up|lifted|raised|hiked)|"
        r"flash\w*\s+(her|his|their)?\s*(breasts?|chest|tits?|boobs?)|"
        r"hik\w*\s+(her|his|their|the)?\s*(shirt|top|skirt|dress)"
    )
    _UNDRESS_RE = re.compile(r"\b(" + _UNDRESS_CORE + r")\b", re.IGNORECASE)
    _SENSUAL_RE = re.compile(
        r"\b(" + _UNDRESS_CORE + r"|"
        r"naked|nude|topless|"
        r"sensual|erotic|intimate|lingerie|bare\s+skin|bare\s+body|"
        r"babydoll|nighty|nightie|negligee|corset|bodysuit|thong|g-string|"
        r"sheer|see-through|teas\w*|seductiv\w*|seduc\w*|"
        r"flirt\w*|provocativ\w*|suggestiv\w*|allur\w*)\b",
        re.IGNORECASE,
    )
    _LIFT_RE = re.compile(
        r"\b(lift\w*\s+(her|his|their|the)?\s*(shirt|top|dress|skirt|crop|tee|t-shirt)|"
        r"(shirt|top|dress|skirt|crop|tee|t-shirt)\s+(?:is\s+|was\s+|gets?\s+)?(up|lifted|raised|hiked|rides?\s+up|bunche\w*\s+up|creep\w*\s+up|pull\w*\s+up|slide\w*\s+up)|"
        r"flash\w*\s+(her|his|their)?\s*(breasts?|chest|tits?|boobs?)|"
        r"hik\w*\s+(her|his|their|the)?\s*(shirt|top|skirt|dress))\b",
        re.IGNORECASE,
    )
    _GARMENT_RE = re.compile(
        r"\b(shirt|t-shirt|tee|top|blouse|crop|camisole|tank\s*top|vest|"
        r"dress|skirt|miniskirt|"
        r"bra|bralette|"
        r"pants|jeans|trousers|shorts|leggings|legging|tights|"
        r"underwear|undies|panties|thong|g-string|knickers|briefs|boxers|"
        r"jacket|coat|blazer|hoodie|sweater|cardigan|jumper|"
        r"robe|kimono|"
        r"bodysuit|jumpsuit|playsuit|catsuit|"
        r"corset|bustier|"
        r"lingerie|nighty|nightie|negligee|babydoll|"
        r"bikini|swimsuit|swimwear|"
        r"stocking|stockings|sock|socks|"
        r"clothes|clothing|outfit)\b",
        re.IGNORECASE,
    )
    _FACING_AWAY_RE = re.compile(
        r"\b(from behind|from the back|rear.?view|back.?view|"
        r"camera behind|shoot(ing)? from behind|filmed? from behind|"
        r"watches? (her|him|them) from behind|follows? (her|him|them) from behind|"
        r"camera follows? (her|him|them)|follow(ing)? her from behind|"
        r"over.{0,6}shoulder from behind|back of (her|his|their) head)\b",
        re.IGNORECASE,
    )
    _FACING_CAMERA_RE = re.compile(
        r"\b(faces? (the )?camera|looks? (at|into) (the )?camera|"
        r"faces? forward|toward (the )?camera|facing (us|viewer|audience)|"
        r"selfie|mirror selfie|talking to camera|front.?facing|facing front)\b",
        re.IGNORECASE,
    )
    _SEQUENCE_RE = re.compile(r"^\s*\d+[\.\):]\s+.+", re.MULTILINE)
    _MOTION_RE = re.compile(
        r"\b(walk\w*|run\w*|mov\w*|turn\w*|lift\w*|bend\w*|reach\w*|pull\w*|push\w*|"
        r"danc\w*|jump\w*|climb\w*|fall\w*|drop\w*|sit\w*|stand\w*|rise\w*|lean\w*|"
        r"nod\w*|shak\w*|wave\w*|stir\w*|pour\w*|open\w*|clos\w*|look\w*|glanc\w*|"
        r"strip\w*|undress\w*|remov\w*|hike\w*|unzip\w*|unbutton\w*|"
        r"crawl\w*|kneel\w*|stretch\w*|sway\w*|bounce\w*|grind\w*|thrust\w*|"
        r"follows?|tracking|panning|dolly|zoom\w*|tilt\w*|orbit\w*|drift\w*)\b",
        re.IGNORECASE,
    )
    _PERSON_RE = re.compile(
        r"\b(he|she|his|her|him|they|them|their|man|men|woman|women|girl|girls|boy|boys|"
        r"guy|guys|person|people|couple|figure|character|model|actress|actor|"
        r"someone|anybody|nobody|stranger|friend|lover|wife|husband|"
        r"boyfriend|girlfriend|teenager|adult|female|male|blonde|brunette|"
        r"redhead|nude|naked|singer|dancer|performer|athlete|soldier|worker|"
        r"player|nurse|doctor|student|teacher|child|children|kid|kids|crowd|audience)\b",
        re.IGNORECASE,
    )
    _MULTI_RE = re.compile(
        r"\b(two\s+(women|men|people|girls|guys|characters|figures|friends|strangers|colleagues|lovers|siblings)|"
        r"both\s+(of\s+them|women|men|girls|guys)|"
        r"(she|he)\s+and\s+(she|he|her|him)|"
        r"(a\s+man\s+and\s+a\s+woman|a\s+woman\s+and\s+a\s+man)|"
        r"couple|trio|they\s+(kiss|touch|embrace|undress|fuck|have)|"
        r"(detective|officer|cop|agent|inspector|boss|manager|doctor|nurse|teacher|interviewer)\s+.{0,50}\s+(suspect|witness|employee|patient|student|client|candidate)|"
        r"a\s+(detective|officer|cop|boss|manager|doctor|nurse|teacher)\s+.{0,80}(a|the)\s+(suspect|witness|employee|patient|student))\b",
        re.IGNORECASE,
    )
    _MUSIC_RE = re.compile(
        r"\b(music|song|track|beat|bass|rhythm|danc\w*|club|rave|party|dj|"
        r"playlist|bpm|groove|vibe|concert|gig|perform\w*|sing\w*|singer|"
        r"strip\w*club|pole danc\w*|lap danc\w*)\b",
        re.IGNORECASE,
    )
    _MALE_RE = re.compile(
        r'\b(he|his|him|man|men|guy|guys|bloke|dude|gentleman|male|boy(?!friend)|boys|'
        r'actor|policeman|fireman|detective(?!\s+and\s+a\s+woman))\b',
        re.IGNORECASE,
    )
    _FEMALE_RE = re.compile(
        r'\b(she|her|hers|woman|women|girl|girls|lady|female|'
        r'actress|policewoman|girlfriend|wife)\b',
        re.IGNORECASE,
    )
    _NON_HUMAN_RE = re.compile(
        r'\b(gorilla|ape|elephant|lion|tiger|bear|wolf|horse|dragon|dinosaur|creature|monster|robot|'
        r'alien|ghost|angel|demon|animal|beast|bird|shark|whale|dolphin|snake|spider)\b',
        re.IGNORECASE,
    )
    _USER_CHAR_RE = re.compile(
        r'\b(a woman|a man|a girl|a boy|a guy|a lady|a person|a figure|a stranger|someone|'
        r'an old man|an old woman|a young woman|a young man|a teenage|a child|'
        r'a detective|a soldier|a doctor|a nurse|a teacher|a dancer|a singer|a model|'
        r'a journalist|a scientist|a chef|a pilot|a cowboy|a priest|a nun|a monk|'
        r'a warrior|a queen|a king|a princess|a prince|a knight|a wizard|a witch|'
        r'a businessman|a businesswoman|a student|a athlete|a boxer|a ballerina)\b'
        r'|\b(\d{1,2})[- ]?year[- ]?old\b'
        r'|\b(blonde|brunette|redhead|black hair|brown hair|dark hair|grey hair|gray hair'
        r'|silver hair|auburn|curly|straight|wavy|afro|braids|pixie|bob|long hair|short hair)\b'
        r'|\b(pale|fair|light|dark|brown|black|tan|olive|caramel|ebony|ivory) skin\b'
        r'|\b(slim|petite|curvy|full.figured|athletic|muscular|stocky|plus.size|thick)\b'
        r'|\b(wearing|dressed in|clad in|in her|in his)\b'
        r'|\b(dress|skirt|jeans|trousers|shirt|blouse|top|coat|jacket|pyjamas|nighty|'
        r'nightgown|lingerie|underwear|bra|panties|tracksuit|hoodie|uniform|suit|gown|robe)\b'
        r'|\b(french|german|italian|spanish|portuguese|russian|ukrainian|polish|dutch|swedish|'
        r'norwegian|danish|finnish|greek|turkish|arabic|arab|egyptian|moroccan|lebanese|'
        r'iranian|persian|indian|pakistani|bangladeshi|thai|vietnamese|indonesian|filipino|'
        r'malaysian|chinese|japanese|korean|taiwanese|brazilian|mexican|colombian|argentinian|'
        r'chilean|peruvian|venezuelan|cuban|jamaican|nigerian|ghanaian|kenyan|ethiopian|'
        r'south african|australian|new zealand|canadian|american|british|irish|scottish|welsh|'
        r'czech|hungarian|romanian|bulgarian|serbian|croatian|slovak|slovenian|'
        r'middle eastern|east asian|south asian|southeast asian|latin|latina|latino|'
        r'scandinavian|nordic|slavic|mediterranean|caucasian)\b',
        re.IGNORECASE,
    )
    # Separate body-style-only regex — used to detect user body overrides for gravure
    _BODY_STYLE_RE = re.compile(
        r'\b(slim|slender|petite|tiny|small|curvy|busty|voluptuous|full.figured|'
        r'athletic|toned|fit|muscular|lean|tall|short|stocky|thick|plus.size|'
        r'hourglass|flat.chested|long.legged|big.butt|small.waist)\b',
        re.IGNORECASE,
    )
    _STREET_SCENE_RE = re.compile(
        r'\b(chav|tracksuit|council|estate|chicken shop|kebab|mcdonalds|mcdonald|'
        r'nando|tesco|lidl|aldi|asda|bus stop|high street|shopping centre|precinct|'
        r'off.?licence|corner shop|market stall|car park|pub|wetherspoon|greggs|'
        r'working.?class|street|pavement|sidewalk|vlog|selfie|phone cam|iphone|'
        r'tiktok|instagram|snapchat|found footage|cctv|security cam|dashcam|'
        r'documentary|reality.?tv|fly.?on.?the.?wall|lo.?fi|low.?fi|gritty|'
        r'raw footage|home video|amateur|naturalistic)\b',
        re.IGNORECASE,
    )
    _CINEMATIC_SCENE_RE = re.compile(
        r'\b(film noir|period piece|sci.?fi|space|galaxy|epic|blockbuster|'
        r'cinemat|drama|thriller|horror film|music video|fashion|editorial|'
        r'35mm|anamorphic|widescreen|studio|production|director)\b',
        re.IGNORECASE,
    )


    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "bypass": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Skip the LLM and pass your text directly to the output.",
                }),
                "user_input": ("STRING", {
                    "multiline": True,
                    "default": "a woman walks slowly toward the camera on a rain-soaked city street at night",
                    "tooltip": "Describe what you want. Can be a rough idea, a sentence, or numbered steps. The LLM expands this into a full cinematic prompt.",
                }),
                "creativity": ([
                    "0.5 - Strict & Literal",
                    "0.8 - Balanced Professional",
                    "1.0 - Artistic Expansion",
                ], {
                    "default": "0.8 - Balanced Professional",
                    "tooltip": "Controls how closely the LLM sticks to your input.",
                }),
                "seed": ("INT", {
                    "default": -1, "min": -1, "max": 2**31 - 1, "step": 1,
                    "display": "number",
                    "tooltip": "Fixed seed for repeatable results. -1 = random.",
                }),
                # NOTE: control_after_generate must be declared here AND in the generate()
                # signature. ComfyUI passes it as a positional argument. Removing it from
                # either place breaks the node.
                "control_after_generate": (["randomize", "fixed", "increment", "decrement"], {
                    "default": "randomize",
                }),
                "invent_dialogue": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "When ON, the LLM invents natural dialogue woven into the scene. When OFF, only uses dialogue you wrote yourself.",
                }),
                "keep_model_loaded": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Deprecated — the node now always offloads after every run to free VRAM for LTX. This toggle is kept for UI compatibility only.",
                }),
                "offline_mode": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Use locally cached models only. Turn OFF to allow auto-download on first run.",
                }),
                "frame_count": ("INT", {
                    "default": 192, "min": 24, "max": 960, "step": 1,
                    "display": "number",
                    "tooltip": "Match to your video LENGTH setting. 24fps = 1 second, so 192 = 8 seconds.",
                }),
                "style_preset": (list(LTX2PromptArchitectQwen.STYLE_PRESETS.keys()), {
                    "default": "None — let the LLM decide",
                    "tooltip": "Sets the visual aesthetic — lighting, camera, colour, mood. Also drives the FPS output pin automatically.",
                }),
                "portrait_mode": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Force 9:16 vertical framing. LTX-2.3 supports native portrait up to 1080x1920.",
                }),
                "local_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Optional: full local path to Huihui-Qwen3.5-9B snapshot folder",
                    "tooltip": "Leave blank to auto-download from HuggingFace on first run.",
                }),
            },
            "optional": {
                "use_scene_context": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Enable or disable scene_context without disconnecting the wire.",
                }),
                "scene_context": ("STRING", {
                    "default": "", "multiline": True,
                    "placeholder": "Optional: vision description from LTX-2 Vision Describe node",
                    "tooltip": "Wire the output from the LTX-2 Vision Describe node here.",
                }),
                "lora_triggers": ("STRING", {
                    "default": "", "multiline": False,
                    "placeholder": "Optional: LoRA trigger words e.g. 'ohwx woman, film grain'",
                    "tooltip": "Paste your LoRA trigger words here. Prepended to every generated prompt automatically.",
                }),
                "width": ("INT", {
                    "default": 0, "min": 0, "max": 7680, "step": 8,
                    "display": "number",
                    "tooltip": "Wire from your WIDTH constant. Used to detect aspect ratio and set framing/camera language automatically. Leave 0 if not wired.",
                }),
                "height": ("INT", {
                    "default": 0, "min": 0, "max": 7680, "step": 8,
                    "display": "number",
                    "tooltip": "Wire from your HEIGHT constant. Used with width to detect portrait/square/wide/scope ratios. Leave 0 if not wired.",
                }),
                "subject_count": ("INT", {
                    "default": 0, "min": 0, "max": 4, "step": 1,
                    "display": "number",
                    "tooltip": "How many people are in the scene. 0 = let the node guess from your text. 1-4 = explicit override. Changes blocking, framing, and spatial instructions.",
                }),
                "negative_bias": ("STRING", {
                    "default": "", "multiline": False,
                    "placeholder": "Optional: things to avoid e.g. 'no rain, no crowd, no slow motion'",
                    "tooltip": "Steer the LLM away from things it defaults to. Also added to the negative prompt.",
                }),
                "shot_angle": ([
                    "None — LLM decides",
                    "Eye-level — neutral, natural",
                    "Low angle — powerful, imposing",
                    "High angle — vulnerable",
                    "Bird's eye — top-down overhead",
                    "Worm's eye — extreme low, looking up",
                    "Dutch angle — tilted, unsettling",
                    "OTS — over the shoulder",
                    "POV — first person",
                    "Profile — side-on",
                    "Three-quarter — 45 degree",
                ], {
                    "default": "None — LLM decides",
                    "tooltip": "Force a specific shot angle. Overrides the preset default. "
                               "Each preset has a built-in default angle — set this to override it.",
                }),
                "camera_movement": ([
                    "None — LLM decides",
                    "Static — locked off",
                    "Handheld — natural shake",
                    "Slow push in",
                    "Pull back — reveal",
                    "Orbit — 360 around subject",
                    "Tracking — follows subject",
                    "Tilt up — bottom to top",
                    "Tilt down — top to bottom",
                    "Truck left — lateral slide",
                    "Truck right — lateral slide",
                    "Whip pan — fast horizontal snap",
                    "Dolly zoom — vertigo effect",
                    "Aerial — drone descending",
                ], {
                    "default": "None — LLM decides",
                    "tooltip": "Force a specific camera movement. Overrides the preset default. "
                               "Each preset has a built-in default movement — set this to override it.",
                }),
                "audio_input": ("AUDIO", {
                    "tooltip": "Wire any ComfyUI AUDIO output here (LoadAudio, TrimAudioDuration, etc). "
                               "The node analyses energy, tempo, frequency character, and optionally transcribes speech via Whisper. "
                               "Results shape the generated prompt to match the audio.",
                }),
                "audio_enabled": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Master switch for audio analysis. Turn OFF to ignore the wired audio entirely — "
                               "useful when audio is permanently wired in your workflow but you don't always want it to influence the prompt.",
                }),
                "use_whisper": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "When ON: uses openai-whisper (tiny model, 39MB, auto-downloads) to transcribe any speech in the audio. "
                               "The transcript is injected into the prompt so the LLM can sync visuals to what is being said. "
                               "Turn OFF for music-only or when you don't need transcription.",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("PROMPT", "PREVIEW", "NEG_PROMPT")
    FUNCTION = "generate"
    CATEGORY = "LTX2"

    def __init__(self):
        self.tokenizer             = None
        self.model                 = None
        self.loaded                = False
        self._stop_token_ids       = []
        self._last_portrait        = False
        self._last_style           = ""
        self._resolved_model_path  = None  # cached after first snapshot_download — avoids HF API call every run

    # ── Model management ──────────────────────────────────────────────────────

    def load_model(self, offline_mode: bool, local_path: str):
        if self.model is not None:
            return

        # Guard: saved workflows may have stored boolean False for this field.
        # Convert to empty string so the "no local path" branch fires correctly.
        if not isinstance(local_path, str) or local_path.strip().lower() in ("false", "none", "0"):
            local_path = ""

        source = local_path.strip() if local_path and local_path.strip() else None

        if not source:
            if offline_mode:
                source = self.MODEL_HF_ID
                print(f"[LTX2-Qwen] Offline mode — will use HF cache only. "
                      f"If model is not already cached this will raise an error: {self.MODEL_HF_ID}")
            elif self._resolved_model_path:
                # Use cached path from a previous run — avoids HF API call every time
                source = self._resolved_model_path
                print(f"[LTX2-Qwen] Using cached model path: {source}")
            else:
                try:
                    from huggingface_hub import snapshot_download
                    print(f"[LTX2-Qwen] Resolving model path (first run)...")
                    source = snapshot_download(self.MODEL_HF_ID, ignore_patterns=["*.gguf"])
                    self._resolved_model_path = source  # cache for subsequent runs
                    print(f"[LTX2-Qwen] Ready at: {source}")
                except Exception as e:
                    print(f"[LTX2-Qwen] snapshot_download failed: {e} — falling back to direct load")
                    source = self.MODEL_HF_ID
        else:
            print(f"[LTX2-Qwen] Local path: {source}")

        self.tokenizer = AutoTokenizer.from_pretrained(
            source, trust_remote_code=True, local_files_only=offline_mode,
        )
        if torch.cuda.is_available():
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        else:
            dtype = torch.float32  # float16 is not supported on CPU
        self.model = AutoModelForCausalLM.from_pretrained(
            source, torch_dtype=dtype, device_map="auto",
            trust_remote_code=True, local_files_only=offline_mode,
        )
        self.model.config.use_cache = True
        self.model.eval()
        self.loaded = True
        self._stop_token_ids = self._build_stop_token_ids()
        if torch.cuda.is_available():
            a = torch.cuda.memory_allocated() / 1024**3
            r = torch.cuda.memory_reserved()  / 1024**3
            print(f"[LTX2-Qwen] Loaded — VRAM: {a:.2f}GB alloc / {r:.2f}GB reserved")
        print(f"[LTX2-Qwen] Ready: {self.MODEL_HF_ID}")

    def unload_model(self):
        if self.model is None:
            return
        print("[LTX2-Qwen] Unloading model...")
        try:
            for _n, module in list(self.model.named_modules()):
                for _p, param in list(module.named_parameters(recurse=False)):
                    try:
                        param.data = torch.empty(0)
                    except Exception:
                        pass
                for _b, buf in list(module.named_buffers(recurse=False)):
                    try:
                        module._buffers[_b] = None
                    except Exception:
                        pass
        except Exception as e:
            print(f"[LTX2-Qwen] Tensor destroy warning: {e}")

        del self.model
        del self.tokenizer
        self.model           = None
        self.tokenizer       = None
        self.loaded          = False
        self._stop_token_ids = []

        gc.collect()
        if torch.cuda.is_available():
            try:
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.empty_cache()
            except Exception as e:
                print(f"[LTX2-Qwen] CUDA flush warning during unload: {e}")

        gc.collect()

        try:
            import comfy.model_management as mm
            mm.unload_all_models()
            mm.soft_empty_cache()
        except Exception:
            pass

        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.empty_cache()
            a = torch.cuda.memory_allocated() / 1024**3
            r = torch.cuda.memory_reserved()  / 1024**3
            print(f"[LTX2-Qwen] VRAM after free: {a:.2f}GB alloc / {r:.2f}GB reserved")

    def _build_stop_token_ids(self) -> list:
        delimiters = [
            "assistant", "user", "system",
            "<|eot_id|>", "<|end_of_turn|>", "<|im_end|>",
            "<end_of_turn>", "[/INST]", "### Human", "### Assistant",
        ]
        # Guard against tokenizers that return None for eos_token_id
        ids = []
        if self.tokenizer.eos_token_id is not None:
            ids.append(self.tokenizer.eos_token_id)
        for s in delimiters:
            enc = self.tokenizer.encode(s, add_special_tokens=False)
            if enc:
                ids.append(enc[0])
        seen, out = set(), []
        for i in ids:
            if i is not None and i not in seen:
                seen.add(i)
                out.append(i)
        print(f"[LTX2-Qwen] Stop token IDs: {out}")
        return out

    # ── Output cleaning ───────────────────────────────────────────────────────

    _PREAMBLE_RE = re.compile(
        r"^(Sure!?|Certainly!?|Absolutely!?|Of course!?|Here(?:'s| is)[\s\S]*?:|"
        r"Great!?|LTX-?2(?:\.\d)?(?:\s+\w+)*\s*prompt\s*:|Prompt\s*:|Output\s*:|Scene\s*:)[^\n]*\n?",
        re.IGNORECASE,
    )
    _ROLE_BLEED_RE = re.compile(
        r"\s*(assistant|user|system|<\|[^|>]*\|>)\s*$",
        re.IGNORECASE,
    )

    @classmethod
    def _clean_output(cls, text: str) -> str:
        text = text.strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        text = cls._PREAMBLE_RE.sub("", text).strip()
        text = cls._ROLE_BLEED_RE.sub("", text).strip()
        text = re.sub(r"\.(assistant|user|system|<\|[^|>]*\|>)\s*\n", ".\n", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*\n+Note:.*$", "", text, flags=re.DOTALL).strip()
        text = re.sub(r"\s*\n+(Please let me know|Let me revise|No further revision|Confirmed\.|"
                      r"Written to meet|The scene is now over|The output ends|The task is|The task was|"
                      r"The goal was|Nothing more|No continuation|No additional|The response does not|"
                      r"It does not continue|It ceases when|Any such statement|"
                      r"Output length:|Action count:|Total time:|Last character:|I avoided|I wrote|"
                      r"I adhered|I hope this|Thank you for your|Please confirm|I submitted|"
                      r"I can revise|feel free to instruct).*$",
                      "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r'\s*(Ended\.\s*\d+\s*actions|'
                      r'\d+\s+actions[\.,]\s*\d+\s+tokens|'
                      r'\d+\s+tokens[\.,]\s*Done|'
                      r'Done\.\s+\d+\s+seconds|'
                      r'Finished\.\s+\d+|'
                      r'Hard stop\..*$)', '', text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r'\.?\s+The total duration.*$', '.', text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r'\.?\s+The (scene\'?s? )?total (duration|running time).*$', '.', text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r'\s*\(\d+\s+seconds?\)\s*$', "", text).strip()
        text = re.sub(r'\s*\(\d+\s+tokens?[^)]*\)', "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r'\s*\n*\d+\s+tokens[\s,].*$', "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r'\[AMBIENT:\s*([^\]]*)\]', r'\1', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'\((?:DOWN|UP|PULL|PUSH|ZOOM|HOLD|FADE|PAN|TILT|TRUCK|DOLLY)[^\)]{0,80}\)', "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r'\[(Kodak|ARRI|Fuji|Film stock|film stock)[^\]]{0,80}\]\s*', "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r'\b(Lens|Camera angle|Focal length|Shutter|Motion blur|Aperture)\s*:\s*[^.\n]{5,120}[.\n]?\s*$',
                      "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s*(In this (peaceful|serene|quiet|tender|intimate|still|languid|tranquil|soft) (moment|scene|instant)[^.]{0,200}\.)\s*$',
                      "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        text = re.sub(r'[,.]?\s*(leaving only (the [a-z ]{3,60}(of|and)[^.]{3,80})\.?)\s*$',
                      ".", text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[,.]?\s*(the (quiet|soft|gentle|only) (satisfaction|warmth|rhythm|rustle|hum|sound|glow) of [^.]{5,80}\.)\s*$',
                      ".", text, flags=re.IGNORECASE).strip()
        text = re.sub(r'\.\s+The scene ends there[^.]*\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+before the scene fades to black[^.]*\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'\.?\s+[Tt]he scene fades to black[^.]*\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+as the scene fades[^.]*\.', '.', text, flags=re.IGNORECASE).strip()
        # Closing-sentence patterns: "ending on the...", "the scene ending mid-breath", "leaving the audience..."
        text = re.sub(r',?\s+ending on (?:the |a )[^.]{5,150}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[.,]?\s+[Tt]he (?:scene|clip|shot|moment|frame) ending[^.]{0,150}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+the (?:lingering|soft|quiet|fading|final) (?:echo|glow|hum|warmth|pulse|ache|question|breath|sigh|friction) of [^.]{5,120}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+leaving (?:the (?:viewer|audience|camera|eye)|her|him|them|us) [^.]{5,120}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+a sense of [^.]{5,80}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+(?:fully immersed|lost in the moment|lost in the \w+)[^.]{0,60}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+(?:pure|sheer)\s+(?:delight|joy|bliss|happiness|sorrow)[^.]{0,60}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+as if (?:she|he|they) (?:finds?|feels?|radiates?|embodies?)[^.]{5,100}\.', '.', text, flags=re.IGNORECASE).strip()
        # Extended scene-ending catches from live testing
        text = re.sub(r'[.,]?\s+ending the (?:sequence|clip|shot|scene|moment|video)[^.]{0,120}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[.,]?\s+completing the (?:third|second|first|final|last|[a-z]+\s)?(?:beat|sequence|moment|arc)[^.]{0,100}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+before the (?:clip|scene|shot|video|frame) continues?[^.]{0,80}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+(?:the )?(?:golden|warm|soft|fading|dying) (?:light|glow|sun) (?:swallows?|consumes?|dissolves?|washes?) (?:the scene|the frame|everything)[^.]{0,60}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[.,]?\s+[Tt]he scene holds? this[^.]{0,120}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[.,]?\s+grounding (?:the|this|her|his) [^.]{5,100} (?:in|into) (?:tactile |physical |quiet )?reality\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[.,]?\s+capturing (?:her|his|their|the|its) [^.]{5,80} (?:whole|entirety|completeness|totality)\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[.,]?\s+capturing (?:the )?(?:suspended|quiet|still|poised|held) [^.]{5,100}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[.,]?\s+[Aa] final[,]? (?:crisp|soft|slow|sharp|deep|low|quiet|long|steady) [^.]{5,80}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[.,]?\s+[Tt]he scene ends? with[^.]{0,300}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[.,]?\s+[Tt]he (?:room|air|space|silence) (?:hangs?|holds?|settles?|thickens?|hums?) (?:with|in)[^.]{0,120}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',\s+(?:save|except|aside)\s+for[^.]{0,30}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'(?<=\.)\s+[Tt]he (?:shot|camera|frame|lens) holds?[^.]{0,250}\.$', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'(?<=\.)\s+(?:She|He|They|It) (?:remains?|stands?|sits?|hangs?|stays?) (?:suspended|frozen|poised|still|there)[^.]{0,200}\.$', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[.,]?\s+waiting for (?:the|her|him|what)[^.]{0,100}\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'\s*[\(\[]\s*$', '', text).strip()
        text = re.sub(r'\.{2,}', '.', text).strip()
        text = re.sub(r'\s{2,}', ' ', text).strip()
        rep = re.search(r'((?:\b\w[\w\'\\-]*\b[\s\.,!?]*){1,6})\1{4,}$', text, flags=re.DOTALL)
        if rep:
            text = text[:rep.start()].strip()
        return text.strip()

    # ── Generate ──────────────────────────────────────────────────────────────

    def generate(
        self,
        bypass, user_input, creativity, seed, control_after_generate,
        invent_dialogue, keep_model_loaded, offline_mode, frame_count,
        style_preset, portrait_mode, local_path,
        use_scene_context=True, scene_context="", lora_triggers="",
        width=0, height=0, subject_count=0, negative_bias="",
        shot_angle="None — LLM decides", camera_movement="None — LLM decides",
        audio_input=None, audio_enabled=True, use_whisper=False,
    ):
        # ── Bypass ────────────────────────────────────────────────────────────
        if bypass:
            if self.model is not None and not keep_model_loaded:
                self.unload_model()
            neg = _build_negative_prompt("", user_input, is_portrait=portrait_mode, style_preset=style_preset)
            return (user_input.strip(), user_input.strip(), neg)

        # ── VRAM prep ─────────────────────────────────────────────────────────
        try:
            import comfy.model_management as mm
            mm.unload_all_models()
            mm.soft_empty_cache()
        except Exception:
            pass
        if torch.cuda.is_available():
            gc.collect()
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.empty_cache()
            a = torch.cuda.memory_allocated() / 1024**3
            r = torch.cuda.memory_reserved()  / 1024**3
            print(f"[LTX2-Qwen] Pre-run VRAM: {a:.2f}GB alloc / {r:.2f}GB reserved")

        self.load_model(offline_mode=offline_mode, local_path=local_path)

        # ── Style preset ──────────────────────────────────────────────────────
        preset_data            = self.STYLE_PRESETS.get(style_preset, ("", False))
        style_instruction_text = preset_data[0]
        is_portrait            = portrait_mode or preset_data[1]
        style_label            = self.PRESET_STYLE_LABEL.get(style_preset, "")

        if style_instruction_text:
            style_instruction = (
                f"\n[STYLE INSTRUCTION — MANDATORY AESTHETIC ANCHOR: {style_instruction_text} "
                f"Every aspect of the output — lighting, camera, colour, pacing, mood — must reflect this style. "
                f"CRITICAL: You MUST begin your output with exactly these words: \"{style_label}\" — "
                f"then continue with the scene description. This label must be the very first words of your output. "
                f"Do not deviate from this style.]"
            )
        else:
            style_instruction = ""

        if is_portrait:
            portrait_instruction = (
                "\n[PORTRAIT MODE — MANDATORY: This is a 9:16 vertical video for mobile. "
                "All framing must be vertical — tight head-to-torso shots. "
                "No wide horizontal establishing shots. Action moves vertically in frame. "
                "Camera stays close. Optimised for TikTok, Reels, Shorts.]"
            )
        else:
            portrait_instruction = ""

        self._last_portrait = is_portrait
        self._last_style    = style_preset

        # ── Seed ──────────────────────────────────────────────────────────────
        if seed != -1:
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)

        # ── Word budget ───────────────────────────────────────────────────────
        # is_gravure needed early for dialogue scene detection
        is_gravure = "gravure" in style_preset.lower()

        real_seconds  = frame_count / 30.0          # 30fps throughout
        action_count  = max(1, min(6, round(real_seconds / 3.5)))
        # 30f=1s→1  90f=3s→1  120f=4s→1  168f=5.6s→2  192f=6.4s→2
        # 240f=8s→2  300f=10s→3  360f=12s→3  480f=16s→5
        LTX_WORD_FLOOR   = 120
        LTX_WORD_CEILING = 400
        token_val        = max(LTX_WORD_FLOOR, min(LTX_WORD_CEILING, action_count * 75 + 100))
        max_tokens       = int(token_val * 1.4)

        # ── Dialogue-focused scene detection ──────────────────────────────────
        # Fires when the primary purpose of the scene is speech — gravure with
        # dialogue enabled, ASMR, talking to camera, direct address scenes.
        # Uses user_input directly here since _combined_input isn't built yet.
        # Changes the pacing model so each beat IS a spoken moment, not physical
        # action with dialogue squeezed alongside.
        _is_dialogue_scene = (
            (is_gravure and invent_dialogue) or
            bool(re.search(
                r'\b(asmr|talking|talks?\s+to\s+(the\s+)?camera|speaks?\s+to|'
                r'addresses|monologue|narrat\w*|whispers?\s+to|speaks?\s+softly|'
                r'says?\s+something|tells?\s+(?:you|us|me|them)|'
                r'explains?|describes?|confesses?|admits?)\b',
                user_input, re.IGNORECASE
            ))
        )

        # Dialogue scenes get a higher word floor — need room for spoken moments
        if _is_dialogue_scene and invent_dialogue:
            token_val = max(token_val, 200)
            max_tokens = int(token_val * 1.4)

        print(f"[LTX2-Qwen] Budget: ~{token_val}w / {max_tokens} max | {real_seconds:.0f}s | {action_count} actions | dialogue_scene={_is_dialogue_scene}")

        if _is_dialogue_scene and invent_dialogue:
            # Dialogue-focused pacing — each beat is a spoken moment
            if action_count == 1:
                pacing_hint = (
                    f"This clip is {real_seconds:.0f} seconds long. "
                    f"Write ONE spoken moment. The character speaks — that IS the scene. "
                    f"Physical description sets the stage, then she speaks. "
                    f"The dialogue and its physical delivery are the primary content, not decoration. "
                    f"HARD STOP after the spoken moment is complete."
                )
            else:
                ordinal = {2: "2nd", 3: "3rd"}.get(action_count, f"{action_count}th")
                pacing_hint = (
                    f"This clip is {real_seconds:.0f} seconds long. "
                    f"Write EXACTLY {action_count} beats — each beat is a SPOKEN MOMENT. "
                    f"Structure: brief physical setup, then she speaks, then her physical reaction. "
                    f"Dialogue is the primary content of every beat — not an afterthought woven in. "
                    f"Each spoken line gets its own beat with a physical delivery note. "
                    f"Space the lines across the clip — do not dump all dialogue in one block. "
                    f"HARD STOP after the {ordinal} spoken beat is complete."
                )
        elif action_count == 1:
            pacing_hint = (
                f"This clip is {real_seconds:.0f} seconds long. "
                f"Write EXACTLY 1 action. One single moment. "
                f"Do not describe anything before or after it. No setup, no resolution. "
                f"HARD STOP after the 1st action. Do not continue."
            )
        else:
            ordinal = {2: "2nd", 3: "3rd"}.get(action_count, f"{action_count}th")
            pacing_hint = (
                f"This clip is {real_seconds:.0f} seconds long. "
                f"Write EXACTLY {action_count} distinct actions — NO MORE THAN {action_count}. "
                f"Each action takes roughly {real_seconds / action_count:.0f} seconds of screen time. "
                f"Do not add setup, backstory, or resolution beyond these {action_count} actions. "
                f"Dialogue is woven into action beats — it does not consume a beat. "
                f"HARD STOP after the {ordinal} action is complete."
            )

        # ── Temperature ───────────────────────────────────────────────────────
        temp_map = {
            "0.5 - Strict & Literal":      0.5,
            "0.8 - Balanced Professional": 0.8,
            "1.0 - Artistic Expansion":    1.0,
        }
        temperature = temp_map.get(creativity, 0.8)

        # ── Content detection ─────────────────────────────────────────────────

        _active_scene_context = scene_context if use_scene_context else ""
        _combined_input = user_input + " " + _active_scene_context

        # ── Audio analysis ────────────────────────────────────────────────────
        _audio_analysis    = {}
        _audio_instruction = ""
        if audio_input is not None and audio_enabled:
            print(f"[LTX2-Qwen] Analysing audio (whisper={'ON' if use_whisper else 'OFF'})...")
            _audio_analysis    = _analyse_audio(audio_input, use_whisper=use_whisper)
            _audio_instruction = _build_audio_instruction(_audio_analysis)
            if _audio_analysis.get("summary"):
                print(f"[LTX2-Qwen] Audio summary: {_audio_analysis['summary'][:120]}")

        is_explicit    = bool(self._EXPLICIT_RE.search(_combined_input))
        is_sensual     = bool(self._SENSUAL_RE.search(_combined_input)) and not is_explicit
        has_undressing = bool(self._UNDRESS_RE.search(_combined_input))

        # Lift fires only when intent is sensual/explicit OR when no innocent purpose is stated.
        # Innocent-purpose phrases (sitting, stepping, avoiding etc.) suppress the sequence
        # so "lifts her dress to sit down" doesn't trigger the exposure sequence.
        _INNOCENT_LIFT_RE = re.compile(
            r"\b(to\s+sit|to\s+step|to\s+walk|to\s+run|to\s+climb|to\s+cross|to\s+avoid|"
            r"to\s+get\s+(in|out|on|off)|to\s+mount|to\s+board|to\s+enter|to\s+exit|"
            r"getting\s+in|getting\s+out|stepping\s+over|stepping\s+into|"
            r"puddle|stairs|step|kerb|curb|bicycle|bike|horse|car|seat|bench|chair|sofa|couch)\b",
            re.IGNORECASE,
        )
        _lift_raw = bool(self._LIFT_RE.search(_combined_input))
        _lift_innocent = bool(_INNOCENT_LIFT_RE.search(_combined_input))
        has_lift = _lift_raw and (is_sensual or is_explicit or not _lift_innocent)

        # ── Aspect ratio detection ────────────────────────────────────────────
        _ratio_class = "landscape"  # default
        _ratio_instruction = ""
        if width and height and width > 0 and height > 0:
            _ratio = width / height
            if _ratio < 0.75:
                _ratio_class = "portrait"
                is_portrait = True  # override portrait_mode regardless of toggle
                _ratio_instruction = (
                    f"\n[ASPECT RATIO: {width}x{height} — PORTRAIT 9:16 VERTICAL. "
                    "Frame is vertical throughout. Tight head-to-torso. Action moves vertically. "
                    "No horizontal sweep. No wide establishing shots. "
                    "CAMERA REFS: do NOT use ARRI, Alexa, Kodak, or any film stock reference. "
                    "If shooting style is naturalistic, describe it as phone or handheld vertical. "
                    "Only medium-format (Hasselblad, Leica) is acceptable if the style is explicitly editorial.]"
                )
            elif _ratio < 1.15:
                _ratio_class = "square"
                _ratio_instruction = (
                    f"\n[ASPECT RATIO: {width}x{height} — SQUARE 1:1. "
                    "Centred composition. Symmetrical staging. Subject fills the square frame. "
                    "CAMERA REFS: only medium-format or Leica appropriate. "
                    "No wide cinematic language. No horizontal sweep.]"
                )
            elif _ratio < 1.85:
                _ratio_class = "landscape"
                _ratio_instruction = (
                    f"\n[ASPECT RATIO: {width}x{height} — LANDSCAPE 16:9 WIDESCREEN. "
                    "Standard cinematic framing. Camera refs depend on scene type — "
                    "street/chav/lo-fi/documentary scenes: describe light source only, no film stock. "
                    "Drama/thriller/sci-fi/epic: ARRI Alexa, Kodak stocks appropriate.]"
                )
            elif _ratio < 2.4:
                _ratio_class = "ultrawide"
                _ratio_instruction = (
                    f"\n[ASPECT RATIO: {width}x{height} — ULTRA-WIDE 21:9. "
                    "Sweeping horizontal space. The frame breathes at the edges. "
                    "Environment is dominant. Build foreground depth. "
                    "CAMERA REFS: RED Monstro, ARRI Alexa 65, anamorphic glass appropriate at this ratio.]"
                )
            else:
                _ratio_class = "anamorphic"
                _ratio_instruction = (
                    f"\n[ASPECT RATIO: {width}x{height} — ANAMORPHIC SCOPE 2.39:1. "
                    "Full scope cinema framing. Anamorphic lens compression. Oval bokeh. "
                    "Horizontal lens flare on light sources. Every frame should feel like a poster. "
                    "CAMERA REFS: Panavision, Cooke anamorphic, ARRI Alexa always appropriate at scope ratio.]"
                )

        # ── Scene-aware camera ref gate ───────────────────────────────────────
        _street_scene        = bool(self._STREET_SCENE_RE.search(_combined_input))
        _cinematic_scene     = bool(self._CINEMATIC_SCENE_RE.search(_combined_input))
        _preset_is_cinematic = any(w in style_preset.lower() for w in [
            'cinematic', 'drama', 'noir', 'sci-fi', 'horror', 'fashion', 'epic',
            'thriller', 'golden hour', 'editorial', 'erotic cinema',
        ])
        _use_camera_ref = (_cinematic_scene or _preset_is_cinematic) and not _street_scene
        if not _use_camera_ref and _ratio_class in ("ultrawide", "anamorphic"):
            _use_camera_ref = True  # scope ratio always earns cinema language

        # ── Subject count override ────────────────────────────────────────────
        # 0 = auto-detect from text (existing behaviour), 1-4 = explicit
        _subject_count_instruction = ""
        if subject_count and subject_count > 0:
            if subject_count == 1:
                _subject_count_instruction = (
                    "\n[SUBJECT COUNT — CONFIRMED: exactly ONE person in this scene. "
                    "Do not add a second person. Single-subject spatial blocking only. "
                    "Anchor them in frame — centre, left, or right — and describe their relationship to the background.]"
                )
            elif subject_count == 2:
                _subject_count_instruction = (
                    "\n[SUBJECT COUNT — CONFIRMED: exactly TWO people in this scene. "
                    "Give each a distinct spatial position — left/right or foreground/background. "
                    "Describe both clearly. Keep their actions non-overlapping. "
                    "Name their relative positions explicitly.]"
                )
            elif subject_count == 3:
                _subject_count_instruction = (
                    "\n[SUBJECT COUNT — CONFIRMED: THREE people in this scene. "
                    "Space them clearly — foreground, mid, background or spread across frame. "
                    "Keep each person's action simple and non-overlapping. "
                    "Clarity of individual positions is mandatory.]"
                )
            elif subject_count >= 4:
                _subject_count_instruction = (
                    f"\n[SUBJECT COUNT — CONFIRMED: {subject_count} people in this scene. "
                    "This is a group scene. Do not attempt to describe each person individually — "
                    "describe the group as a mass with notable individuals pulled into focus. "
                    "Use wide or establishing framing.]"
                )

        # ── Camera lock ───────────────────────────────────────────────────────
        # ── Camera angle + movement ───────────────────────────────────────────
        # Priority order:
        #   1. User widget explicitly set → always MANDATORY, overrides everything
        #   2. User wrote camera terms in prompt → suppress preset default for that axis
        #      (respect what they wrote, don't fight them with a MANDATORY tag)
        #   3. Preset default → inject if no user text conflict
        _preset_cam = self.PRESET_CAMERA_DEFAULTS.get(style_preset, (None, None))
        _preset_angle    = _preset_cam[0]
        _preset_movement = _preset_cam[1]

        # Detect camera angle/movement terms written by the user in their prompt
        _USER_ANGLE_RE = re.compile(
            r"\b(low angle|high angle|eye.?level|bird.?s.?eye|worm.?s.?eye|dutch angle|"
            r"over.the.shoulder|OTS|point of view|POV|first.?person|side.?on|profile shot|"
            r"top.?down|overhead shot|looking up|looking down|canted|tilted frame)\b",
            re.IGNORECASE,
        )
        _USER_MOVEMENT_RE = re.compile(
            r"\b(static|locked.?off|handheld|hand.?held|dolly|push in|pull back|pull away|"
            r"zoom in|zoom out|orbit|tracking shot|track\w*\s+(?:her|him|them|the)|"
            r"tilt up|tilt down|pan left|pan right|whip pan|truck|lateral|aerial|drone|"
            r"slow pan|slow push|crane shot|steadicam|gimbal)\b",
            re.IGNORECASE,
        )

        _user_wrote_angle    = bool(_USER_ANGLE_RE.search(_combined_input))
        _user_wrote_movement = bool(_USER_MOVEMENT_RE.search(_combined_input))

        # Widget explicitly set → always use it (user made a deliberate choice)
        _widget_angle_set    = shot_angle    != "None — LLM decides"
        _widget_movement_set = camera_movement != "None — LLM decides"

        # Resolve effective angle: widget > preset (if no user text conflict) > None
        if _widget_angle_set:
            _eff_angle = shot_angle
        elif _user_wrote_angle:
            _eff_angle = None   # user described it themselves — don't override
        else:
            _eff_angle = _preset_angle

        # Resolve effective movement: widget > preset (if no user text conflict) > None
        if _widget_movement_set:
            _eff_movement = camera_movement
        elif _user_wrote_movement:
            _eff_movement = None  # user described it themselves — don't override
        else:
            _eff_movement = _preset_movement

        _ANGLE_INSTRUCTIONS = {
            "Eye-level — neutral, natural":    "SHOT ANGLE — MANDATORY: eye-level. Camera at the subject's eye height. Natural, neutral perspective. No tilt up or down.",
            "Low angle — powerful, imposing":  "SHOT ANGLE — MANDATORY: low angle. Camera positioned below the subject, pointing upward. Subject appears powerful, dominant, imposing.",
            "High angle — vulnerable":         "SHOT ANGLE — MANDATORY: high angle. Camera above the subject, pointing down. Subject appears small, vulnerable, or surveilled.",
            "Bird's eye — top-down overhead":  "SHOT ANGLE — MANDATORY: bird's eye view. Camera directly overhead, pointing straight down. Subject seen from above.",
            "Worm's eye — extreme low, looking up": "SHOT ANGLE — MANDATORY: worm's eye view. Camera at ground level or below, looking steeply upward. Extreme perspective distortion.",
            "Dutch angle — tilted, unsettling": "SHOT ANGLE — MANDATORY: Dutch angle. Camera tilted on its horizontal axis — frame is deliberately canted. Psychological unease.",
            "OTS — over the shoulder":         "SHOT ANGLE — MANDATORY: over-the-shoulder. Camera behind one character's shoulder, framing the other. Classic two-person composition.",
            "POV — first person":              "SHOT ANGLE — MANDATORY: POV / first-person. The camera IS the eyes of the subject. We see what they see. No third-person framing.",
            "Profile — side-on":               "SHOT ANGLE — MANDATORY: profile shot. Camera positioned exactly to the side of the subject. Subject faces left or right, fully in profile.",
            "Three-quarter — 45 degree":       "SHOT ANGLE — MANDATORY: three-quarter angle. Camera at roughly 45 degrees to the subject — between full-face and profile.",
        }

        _MOVEMENT_INSTRUCTIONS = {
            "Static — locked off":             "CAMERA MOVEMENT — MANDATORY: completely static and locked off. No push, no drift, no sway, no zoom. The frame does not move at all. All motion comes from the subject and environment only.",
            "Handheld — natural shake":        "CAMERA MOVEMENT — MANDATORY: handheld. Natural human sway, slight vertical bounce, micro-rotations. The camera breathes with the operator. Never smooth or gimbal-stabilised.",
            "Slow push in":                    "CAMERA MOVEMENT — MANDATORY: slow, deliberate push toward the subject. The shot begins wider and tightens imperceptibly over the duration. No other camera movement.",
            "Pull back — reveal":              "CAMERA MOVEMENT — MANDATORY: the camera pulls back slowly, revealing the wider environment around the subject. Begin tight, end wide. The reveal is the payoff.",
            "Orbit — 360 around subject":      "CAMERA MOVEMENT — MANDATORY: the camera orbits the subject in a slow 360-degree arc. Subject stays centred as the background rotates behind them. Smooth and continuous.",
            "Tracking — follows subject":      "CAMERA MOVEMENT — MANDATORY: the camera tracks with the subject as they move. Subject stays roughly centred in frame. Camera matches their speed and direction. No static holds.",
            "Tilt up — bottom to top":         "CAMERA MOVEMENT — MANDATORY: the camera tilts upward, beginning at the subject's feet or lower body and rising slowly to their face. No horizontal movement.",
            "Tilt down — top to bottom":       "CAMERA MOVEMENT — MANDATORY: the camera tilts downward, beginning at the subject's face and descending slowly to their feet or lower body.",
            "Truck left — lateral slide":      "CAMERA MOVEMENT — MANDATORY: the camera trucks/slides laterally to the left, maintaining its facing direction. Subjects pass through frame left-to-right as the camera moves.",
            "Truck right — lateral slide":     "CAMERA MOVEMENT — MANDATORY: the camera trucks/slides laterally to the right, maintaining its facing direction. Subjects pass through frame right-to-left as the camera moves.",
            "Whip pan — fast horizontal snap": "CAMERA MOVEMENT — MANDATORY: whip pan. The camera snaps hard and fast horizontally to reveal a new subject or beat. Motion blur during the snap, sharp before and after.",
            "Dolly zoom — vertigo effect":     "CAMERA MOVEMENT — MANDATORY: dolly zoom (Hitchcock/vertigo effect). The camera physically moves toward the subject while the focal length simultaneously widens, or vice versa. Background appears to grow or shrink unnaturally.",
            "Aerial — drone descending":       "CAMERA MOVEMENT — MANDATORY: aerial perspective. Camera begins high above, looking down, and descends slowly toward the subject. Subject grows from a small shape to full frame.",
        }

        _camera_lock_instruction = ""
        if _eff_angle or _eff_movement:
            _angle_text    = _ANGLE_INSTRUCTIONS.get(_eff_angle, "") if _eff_angle else ""
            _movement_text = _MOVEMENT_INSTRUCTIONS.get(_eff_movement, "") if _eff_movement else ""
            _source_note   = ""
            if shot_angle == "None — LLM decides" and _eff_angle:
                _source_note += f" [preset default angle for {style_preset}]"
            if camera_movement == "None — LLM decides" and _eff_movement:
                _source_note += f" [preset default movement for {style_preset}]"
            _cam_parts = [p for p in [_angle_text, _movement_text] if p]
            _camera_lock_instruction = "\n[" + " — ".join(_cam_parts) + "]"

        # ── Negative bias ─────────────────────────────────────────────────────
        _negative_bias_instruction = ""
        if negative_bias and negative_bias.strip():
            _negative_bias_instruction = (
                f"\n[AVOID — USER SPECIFIED: {negative_bias.strip()}. "
                "Do not include any of these elements in the scene. "
                "If the style would normally default to them, omit them.]"
            )

        # Build garment list — ONLY garments being actively removed, not merely worn or lifted.
        # Proximity check: a removal verb must appear within 45 chars of the garment.
        # Lift verbs (rides up, hiked, lifted) are intentionally excluded — those trigger
        # the lift instruction, not an undress sequence.
        _REMOVAL_PROXIMITY_RE = re.compile(
            r"\b(undress\w*|strip\w*|takes?\s+off|took\s+off|removes?\w*|"
            r"disrobe\w*|unbutton\w*|unzip\w*|peels?\s+off|pulls?\s+off|"
            r"shed\w*\s+(her|his|their)?)\b",
            re.IGNORECASE,
        )
        _REVEAL_CONTEXT_RE = re.compile(
            r"\b(underneath|beneath|under|reveals?|beneath|exposed\s+underneath)\b",
            re.IGNORECASE,
        )
        named_garments = []
        for m in self._GARMENT_RE.finditer(_combined_input):
            start   = max(0, m.start() - 45)
            end     = min(len(_combined_input), m.end() + 45)
            context = _combined_input[start:end]
            # Must have a removal verb nearby
            if not _REMOVAL_PROXIMITY_RE.search(context):
                continue
            # Exclude garments that appear in a "revealed underneath" context
            # Only exclude if "underneath/beneath/under" appears within 12 chars
            # (e.g. "lingerie underneath" but NOT "blouse, [lingerie underneath]")
            after_context = _combined_input[m.end():min(len(_combined_input), m.end() + 12)]
            if _REVEAL_CONTEXT_RE.search(after_context):
                continue
            g = m.group(0).lower()
            if g not in named_garments:
                named_garments.append(g)
        garment_list = ", ".join(named_garments) if named_garments else ""

        if is_explicit:
            # Only inject undressing sequence if garments are actively being removed.
            # named_garments is empty if no garment appears near a removal verb —
            # e.g. "dress rides up" or "wearing a dress" alone won't populate it.
            if named_garments:
                _undressing_clause = (
                    f"\n\nUNDRESSING SEQUENCE — the user's garments are: {garment_list}. "
                    "Write a dedicated undressing segment BEFORE any nudity. One sentence per step. Camera lingers on each reveal. "
                    "Follow ONLY the steps for the garments the user named. "
                    "\n— T-shirt/shirt/tee/crop top (full off): grip hem at waist → lift past stomach → past ribs → over chest → over head → off arms → dropped. "
                    "\n— T-shirt/shirt/tee/crop top (lift only): grip hem → gather upward → past navel → past ribs → chest and breasts fully exposed → held there. "
                    "\n— Camisole/tank top/vest: slip straps off each shoulder → fabric pools at waist → pushed down → dropped. "
                    "\n— Blouse/button-down: each button one at a time from top to bottom → fabric parts → off shoulders → down arms → dropped. "
                    "\n— Hoodie/sweater/cardigan/jumper: grip hem → pull up and over head → arms free → dropped. "
                    "\n— Jacket/blazer/coat: slide off one shoulder → then the other → down arms → dropped or left hanging. "
                    "\n— Robe/kimono: untie belt → sash falls loose → fabric slides off both shoulders → pools on the floor. "
                    "\n— Dress (zip): reach behind → fingers find zip tab → pull slowly down → fabric parts down the back → off shoulders → slides down body → falls. "
                    "\n— Dress (pullover/slip): grip hem at thighs → gather upward → over hips → over waist → over chest → over head. "
                    "\n— Skirt (zip): find zip at side or back → pull down → waistband loosens → pushed over hips → falls. "
                    "\n— Skirt (elastic): thumbs in waistband → pushed down over hips → falls. "
                    "\n— Miniskirt: as skirt above — very little fabric, falls quickly. "
                    "\n— Jeans/trousers/pants: undo button → pull zip down → push over hips → down thighs → stepped out one leg at a time. "
                    "\n— Shorts: thumbs in waistband → pushed down → stepped out. "
                    "\n— Leggings/tights: both hands at waistband → rolled down from hips → past thighs → off. "
                    "\n— Bra: reach behind → unhook clasp → straps slip off each shoulder → cups fall away → dropped. "
                    "\n— Bralette: grip hem at bottom → pull up and over head → dropped. "
                    "\n— Underwear/panties/knickers/briefs/thong/g-string: thumbs in waistband at hips → pushed down → stepped out. "
                    "\n— Bodysuit/catsuit: unsnap crotch fasteners → pull shoulder straps off → peel down body. "
                    "\n— Jumpsuit/playsuit: unzip or unbutton front → slide straps off shoulders → push down body → step out. "
                    "\n— Corset/bustier: unlace back ties → busk clasps front one by one → removed. "
                    "\n— Bikini top: reach behind → unhook clasp (or untie string) → straps off → removed. "
                    "\n— Bikini bottoms: untie strings at hips or thumbs in waistband → removed. "
                    "\n— Swimsuit/one-piece: straps off shoulders → peeled down body → stepped out. "
                    "\n— Stockings: roll top down from thigh → peel down leg → off foot. "
                    "\n— Lingerie set/negligee/babydoll/nighty: treat as bra + underwear if two-piece, or as slip dress if one-piece. "
                    "\nNO INVENTED RESOLUTION: what comes off stays off. Do not reverse or undo any action. "
                )
            else:
                _undressing_clause = (
                    "\n\nNO GARMENTS: The user described the subject as already naked/nude. "
                    "Do NOT invent clothing to remove. Start the scene with the body already exposed. "
                    "Do NOT add a strip or undress sequence. "
                )
            explicit_instruction = (
                "\n[CONTENT INSTRUCTION — EXPLICIT ADULT SCENE: "
                "Use direct anatomical language exactly as the user wrote it. "
                "If they said 'pussy' write 'pussy'. If they said 'cock' write 'cock'. Never substitute euphemisms. "
                "\n\nCAMERA — MANDATORY even in explicit scenes: name the shot scale (close-up, medium close-up, medium shot, etc). "
                "Always add natural motion blur and smooth movement. "
                "Avoid high frequency patterns in any surface, fabric, or background. "
                "Do NOT reference ARRI, Alexa, Kodak, RED, film stocks, or any cinema camera brand. "
                "Describe lighting in plain terms only: soft, warm, harsh, diffused, side-lit, back-lit. "
                "\n\nSCOPE — ABSOLUTE CEILING: "
                "Describe ONLY what the user explicitly wrote. Nothing beyond. "
                "Do NOT add sexual acts, nudity, or body exposure the user did not state. "
                "One garment requested = one garment removed. The scene ends where the user's words end. "
                "\n\nSOUND IS MANDATORY: Every scene must have sound. "
                "Always state character age as a specific number."
                + _undressing_clause + "]"
            )
        elif is_sensual:
            # Detect if user described subject as already naked/nude/topless
            _already_exposed = bool(re.search(
                r'\b(naked|nude|topless|undressed|bare|nothing\s+on|no\s+clothes)\b',
                _combined_input, re.IGNORECASE
            ))
            if has_undressing:
                if named_garments:
                    # Detect if user asked for partial open (unbutton/unzip but no removal verb)
                    # vs full removal (removes/takes off/pulls off etc.)
                    _partial_open = bool(re.search(
                        r'\b(unbutton\w*|unzip\w*|open\w*|parts?\s+her|loosens?\w*|undoes?\w*)\b',
                        _combined_input, re.IGNORECASE
                    )) and not bool(re.search(
                        r'\b(takes?\s+off|took\s+off|removes?\w*|pulls?\s+off|peels?\s+off|'
                        r'shed\w*|drop\w*|strip\w*)\b',
                        _combined_input, re.IGNORECASE
                    ))
                    _partial_note = (
                        "\n\nPARTIAL OPEN ONLY: The user asked to unbutton/open — NOT to remove. "
                        "The garment stays ON the body, hanging open or parted. "
                        "Do NOT write it being pulled off, dropped, or falling away. "
                        "It opens, reveals what's underneath, and STAYS. "
                    ) if _partial_open else ""
                    undress_clause = (
                        f"\n\nUNDRESSING — SCOPE CEILING: User named these garments only: {garment_list}. "
                        f"Remove ONLY those. Nothing beyond. "
                        f"Do NOT advance from shirt → bra unless user said bra. "
                        f"Do NOT advance from bra → topless unless user said topless or nude. "
                        f"The named garments are the ceiling. Style preset does NOT override this. "
                        + _partial_note +
                        f"\n\nSOUND IS MANDATORY throughout — fabric sounds, breathing, environment. "
                        f"\n\nFor each garment write every physical step as its own sentence. "
                        "Follow ONLY the steps for the garments the user named. "
                        "\n— T-shirt/shirt/tee/crop top (full off): grip hem at waist → lift past stomach → past ribs → over chest → over head → off arms → dropped. "
                        "\n— T-shirt/shirt/tee/crop top (lift only): grip hem → gather upward → past navel → past ribs → chest fully exposed → held there. "
                        "\n— Camisole/tank top/vest: slip straps off each shoulder → fabric pools at waist → pushed down → dropped. "
                        "\n— Blouse/button-down: each button top to bottom → fabric parts → off shoulders → down arms → dropped. "
                        "\n— Hoodie/sweater/cardigan/jumper: grip hem → pull up and over head → arms free → dropped. "
                        "\n— Jacket/blazer/coat: slide off one shoulder → then the other → down arms → dropped. "
                        "\n— Robe/kimono: untie belt → sash falls loose → fabric slides off both shoulders → pools on the floor. "
                        "\n— Dress (zip): find zip behind → pull slowly down → fabric parts → off shoulders → slides down body → falls. "
                        "\n— Dress (pullover): grip hem at thighs → over hips → over waist → over chest → over head. "
                        "\n— Skirt (zip): find zip at side or back → pull down → pushed over hips → falls. "
                        "\n— Skirt (elastic/miniskirt): thumbs in waistband → pushed down over hips → falls. "
                        "\n— Jeans/trousers/pants: undo button → pull zip → push over hips → down thighs → stepped out. "
                        "\n— Shorts: thumbs in waistband → pushed down → stepped out. "
                        "\n— Leggings/tights: both hands at waistband → rolled down from hips → off. "
                        "\n— Bra: reach behind → unhook clasp → straps off each shoulder → cups fall away. "
                        "\n— Bralette: grip hem → pull over head → dropped. "
                        "\n— Underwear/panties/knickers/briefs/thong/g-string: thumbs in waistband → pushed down → stepped out. "
                        "\n— Bodysuit/catsuit: unsnap crotch → pull straps off → peel down body. "
                        "\n— Jumpsuit/playsuit: unzip/unbutton front → push down body → step out. "
                        "\n— Corset/bustier: unlace back → busk clasps front → removed. "
                        "\n— Bikini top: unhook or untie → removed. "
                        "\n— Bikini bottoms: untie strings or thumbs in waistband → removed. "
                        "\n— Swimsuit: straps off shoulders → peeled down body → stepped out. "
                        "\n— Stockings: roll top down from thigh → peel down leg → off. "
                        "\n— Lingerie/negligee/babydoll/nighty: treat as bra+underwear if two-piece, or slip dress if one-piece. "
                        "\nCamera holds on each reveal. STOP after the last named garment. "
                        "NO INVENTED RESOLUTION: do not reverse or cover any action unless the user asked."
                    )
                else:
                    # Strip/undress verb used but no garments named — already naked scenario
                    undress_clause = (
                        "\n\nNO GARMENTS NAMED: The user used a strip/undress verb but named no specific "
                        "clothing. Treat the subject as already naked or nearly so. "
                        "Do NOT invent garments to remove. Do NOT write a progressive undressing sequence. "
                        "Do NOT describe fabric falling, clothing being lifted, or any reveal. "
                        "Start the scene with the body already exposed and describe movement, atmosphere, "
                        "and mood only. Sound and environment fill the gap — not invented clothing. "
                        "\n\nSOUND IS MANDATORY — breathing, environment, movement sounds."
                    )
            elif _already_exposed:
                # naked/nude/topless with no undress action — body is just present
                undress_clause = (
                    "\n\nALREADY EXPOSED: User described the subject as naked/nude/topless. "
                    "The body is already uncovered — there is no clothing to remove. "
                    "Do NOT add any undressing sequence. Do NOT invent clothing. "
                    "Describe the body, pose, and scene as written. "
                    "\n\nSOUND IS MANDATORY — breathing, environment. Never silent."
                )
            else:
                undress_clause = (
                    "\n\nNO UNDRESSING: User has not asked for clothing removal. "
                    "Do NOT remove, loosen, or sexualise any clothing. "
                    "Stay exactly at the level of sensuality the user described — no further. "
                    "\n\nSOUND IS MANDATORY — environment, clothing movement, breathing. Never silent."
                )
            explicit_instruction = (
                "\n[CONTENT INSTRUCTION — SENSUAL SCENE: "
                "Tone: warm, cinematic, tasteful. "
                "SCOPE — ABSOLUTE CEILING: Describe ONLY what the user asked for. Do NOT self-escalate. "
                "Style preset controls aesthetics only — it does NOT give permission to add content. "
                "SOUND IS MANDATORY: every beat needs sound. "
                "Always state character age as a specific number. "
                + undress_clause + "]"
            )
        else:
            _cam_ref_line = (
                "(1) Style and genre. Weave film stock or camera reference into prose naturally — "
                "e.g. 'carries a Kodak 2383 warmth', 'ARRI Alexa clean look'. NEVER as a bracketed tag. "
            ) if _use_camera_ref else (
                "(1) Style and genre — describe the aesthetic in plain terms: lighting quality, colour temperature, "
                "grain or sharpness, overall mood. Do NOT reference ARRI, Kodak, film stocks, or cinema cameras. "
            )
            explicit_instruction = (
                "\n[INSTRUCTION — CINEMATIC LTX-2.3 PROMPT: "
                "LTX-2.3 handles complexity well — be specific, do not simplify. "
                "Build the prompt in this order: "
                + _cam_ref_line +
                "(2) Shot scale and framing — name it clearly: extreme close-up, close-up, medium close-up, medium shot, medium wide, wide shot, establishing shot, low angle, high angle, Dutch angle, OTS, POV. "
                "Always add natural motion blur. "
                "(3) Character — age as a number always, default 18–35. "
                "Hair texture and colour, skin tone, body type, clothing with fabric and material detail. "
                "Include subtle micro expressions and emotional cues. "
                "(4) Spatial blocking — explicit left/right/fore/background, who faces what, distances stated. "
                "(5) Environment — location, lighting direction, surface textures. "
                "Avoid high frequency patterns in clothing, walls, floors. "
                "(6) Action — VERBS: who moves, what moves, how, what the camera does simultaneously. "
                "(7) Texture in motion — how materials behave as things move. "
                "(8) Camera movement — prose verbs only: 'the shot pushes in slowly', never bracketed. "
                "(9) Sound — MANDATORY, physical and concrete, max 2 per beat. Never silent.]"
            )

        # ── Camera orientation detection ──────────────────────────────────────
        is_facing_away   = bool(self._FACING_AWAY_RE.search(_combined_input))
        is_facing_camera = bool(self._FACING_CAMERA_RE.search(_combined_input))

        if style_preset == "Voyeur — handheld, observational" and not is_facing_camera:
            is_facing_away = True

        if is_facing_away and not is_facing_camera:
            voyeur_height = (
                " Camera held at hip or chest height — low and discreet, never raised for a clean angle."
                if style_preset == "Voyeur — handheld, observational" else ""
            )
            orientation_instruction = (
                "\n\n[CAMERA ORIENTATION — MANDATORY: "
                "The user has explicitly asked for a rear/behind view. "
                "The subject faces AWAY from the camera throughout. "
                "The camera sees her back, the back of her head, and the rear of her body."
                + voyeur_height +
                " Open your output with the orientation stated clearly. "
                "No front-facing shots. No face visible. Rear view for the entire scene.]"
            )
        else:
            orientation_instruction = ""

        # ── Sequence detection ────────────────────────────────────────────────
        # _SEQUENCE_RE uses no capture group so findall returns full match strings.
        sequence_steps = self._SEQUENCE_RE.findall(_combined_input)
        if len(sequence_steps) >= 2:
            step_count = len(sequence_steps)
            sequence_instruction = (
                f"\n[SEQUENCE INSTRUCTION: The user has provided {step_count} numbered steps. "
                f"You MUST follow them in exact order. Do not reorder, skip, or merge steps. "
                f"Do not add actions before step 1 or after step {step_count}.]"
            )
        else:
            sequence_instruction = ""

        # ── Anti-static detection ─────────────────────────────────────────────
        if not bool(self._MOTION_RE.search(_combined_input)):
            static_instruction = (
                "\n\n[MOTION INSTRUCTION: The user's input has no explicit motion verbs. "
                "Add directed movement — camera first: a slow push in, a gentle track, a creeping orbit. "
                "Then one subject action if it fits: a head turn, a step forward, a glance to the side. "
                "Only if neither applies, add a single environmental detail: wind moving hair, a background figure. "
                "LTX-2.3 holds complex motion — use verbs of progression, not filler.]"
            )
        else:
            static_instruction = ""

        # ── Person detection ──────────────────────────────────────────────────
        # Use _active_scene_context (respects use_scene_context flag) not raw scene_context
        has_person = bool(self._PERSON_RE.search(user_input + " " + _active_scene_context))
        if not has_person:
            no_person_instruction = (
                "\n[SCENE INSTRUCTION: No person or character in this scene. "
                "Do NOT invent human figures, silhouettes, voices, or implied presence. "
                "Write only the setting, objects, light, and motion of non-human elements. "
                "SOUND IS STILL MANDATORY: environmental sound only — wind, water, machinery, rain, animals.]"
            )
        else:
            no_person_instruction = ""

        # ── Multi-subject detection ───────────────────────────────────────────
        # Use _active_scene_context (respects use_scene_context flag)
        if bool(self._MULTI_RE.search(user_input + " " + _active_scene_context)):
            multi_instruction = (
                "\n[MULTI-SUBJECT INSTRUCTION: This scene has two or more people. "
                "For EACH person establish: their position in the frame, their spatial relationship to the other, "
                "and keep track of who is doing what throughout using consistent descriptors.]"
            )
        else:
            multi_instruction = ""

        # ── Music / dance detection ───────────────────────────────────────────
        has_music = bool(self._MUSIC_RE.search(_combined_input))
        if has_music:
            music_sound_rule = (
                "SOUND — MUSIC SCENE: Describe the music as physical sensation and sound. "
                "Not 'music plays' — give it body: 'a deep kick drum at 128bpm punches through the floor, sub-bass felt in the chest'. "
                "Describe tempo, weight, texture. Max 2 additional sounds alongside the music. Do NOT silence the music."
            )
        else:
            music_sound_rule = (
                "SOUND — describe with tone, intensity, and environment. "
                "Not 'footsteps' — 'the sharp rhythmic clack of heels on cold tile'. "
                "Max 2 sounds active per beat. Physical sound only, described fully."
            )

        # ── Gravure flag (set early above for word budget, confirmed here) ────
        is_gravure = "gravure" in style_preset.lower()

        # ── Gravure dialogue pools ─────────────────────────────────────────────
        # Three tiers per language: tasteful / sensual / explicit.
        # Explicit tier only sampled when is_explicit=True.
        # Singing pool used when _is_singing=True — lyric fragments, not speech.
        # Format: (native_script, romanisation, physical_delivery_note, tier)
        # tier: 'T' = tasteful, 'S' = sensual, 'X' = explicit

        _GRV_LINES_JAPANESE = [
            # ── Tasteful ──────────────────────────────────────────────────────
            ('「ねえ、見てる?」',           'Nee, miteru?',               'she murmurs, tilting her chin up toward the lens, lips barely parting', 'T'),
            ('「こっち向いて」',             'Kocchi muite',               'she breathes, shifting her weight slowly onto one hip', 'T'),
            ('「こんな私、どう思う?」',       'Konna watashi, dou omou?',   'she asks, head tilting gently, a faint curve at the corner of her mouth', 'T'),
            ('「恥ずかしい…」',             'Hazukashii...',               'she whispers, glancing down then back up, cheeks flushed soft pink', 'T'),
            ('「ずっとそこにいて」',          'Zutto soko ni ite',          'she murmurs, her gaze holding steady on the lens', 'T'),
            ('「あなたのこと、考えてた」',    'Anata no koto, kangaeteta',  'she admits, voice low, eyes dropping briefly before lifting back to the lens', 'T'),
            ('「なんで、そんなに見るの?」',   'Nande, sonna ni miru no?',   'she asks, half-smiling, eyes narrowing playfully', 'T'),
            ('「ここにいるから」',            'Koko ni iru kara',           'she says quietly, settling her weight back, unhurried', 'T'),
            ('「離れないで」',               'Hanarenaide',                'she murmurs, voice catching slightly on the last syllable', 'T'),
            ('「そんな顔しないで」',          'Sonna kao shinaide',         'she says softly, a faint laugh behind the words', 'T'),
            ('「声、聞きたい」',             'Koe, kikitai',               'she says, barely audible, fingers brushing her own shoulder', 'T'),
            ('「あなただけに見せてる」',      'Anata dake ni miseteru',     'she says softly, leaning slightly forward', 'T'),
            ('「もっと近くで見て」',          'Motto chikaku de mite',      'she says softly, her fingers trailing lightly across her collarbone', 'T'),
            ('「全部見てて」',               'Zenbu mitete',               'she whispers, her chin dropping slowly as she holds the gaze', 'T'),
            ('「ねえ、もっとだけ」',          'Nee, motto dake',            'she murmurs, drawing the last word out slowly', 'T'),
            # ── Sensual ───────────────────────────────────────────────────────
            ('「触れてもいいよ」',            'Furete mo ii yo',            'she says quietly, the words barely above a breath, gaze direct', 'S'),
            ('「もっと見せてあげる」',         'Motto misete ageru',         'she says with quiet confidence, shifting her posture deliberately', 'S'),
            ('「もっと欲しい?」',             'Motto hoshii?',              'she breathes, her lip curling into the faintest smile', 'S'),
            ('「今夜は、あなたのもの」',       'Konya wa, anata no mono',    'she breathes, the words deliberate and slow', 'S'),
            ('「気持ちいい…」',               'Kimochi ii...',              'she exhales slowly, eyes closing for a beat before opening again', 'S'),
            ('「もっと奥まで…」',             'Motto oku made...',          'she breathes, the words trailing into a soft exhale', 'S'),
            ('「ゆっくりして」',              'Yukkuri shite',              'she says softly, fingers pressing lightly against his chest', 'S'),
            ('「見られてる、好き」',           'Mirareteru, suki',           'she admits, voice low, a slow smile forming', 'S'),
            ('「もっと強く」',                'Motto tsuyoku',              'she breathes, arching slightly into the touch', 'S'),
            ('「全部感じてる」',              'Zenbu kanjiteru',            'she exhales, barely above silence, eyes half-closed', 'S'),
            ('「あなたに、全部あげる」',       'Anata ni, zenbu ageru',      'she says, the words deliberate, gaze unwavering', 'S'),
            ('「こんなにされたら、止まれない」', 'Konna ni saretara, tomarenai', 'she breathes, her voice unsteady at the edges', 'S'),
            # ── Explicit ──────────────────────────────────────────────────────
            ('「もっと激しく」',              'Motto hageshiku',            'she moans softly, fingers gripping the sheets', 'X'),
            ('「そこ、気持ちいい」',           'Soko, kimochi ii',           'she breathes, hips shifting upward into the pressure', 'X'),
            ('「もっと、もっと奥に」',          'Motto, motto oku ni',        'she gasps, the words breaking apart on the last syllable', 'X'),
            ('「やだ、もう…イく」',            'Yada, mou... iku',           'she whimpers, thighs pressing together', 'X'),
            ('「抜かないで」',                'Nukanaide',                  'she breathes urgently, hands pulling him closer', 'X'),
            ('「全部、飲み込んであげる」',      'Zenbu, nomikonde ageru',     'she says with quiet intensity, holding the gaze', 'X'),
        ]

        _GRV_LINES_KOREAN = [
            # ── Tasteful ──────────────────────────────────────────────────────
            ('\"봐봐, 여기야\"',              'bwa bwa, yeogiya',           'she breathes, tapping her collarbone lightly with one finger', 'T'),
            ('\"나 어때?\"',                  'na eottae?',                 'she asks, tilting her head, a soft half-smile forming', 'T'),
            ('\"좀 더 가까이 와\"',            'jom deo gakkai wa',          'she murmurs, shifting forward slightly on her heels', 'T'),
            ('\"계속 봐줘\"',                  'gyesok bwajwo',              'she says quietly, her gaze direct and unhurried', 'T'),
            ('\"창피해…\"',                   'changpihae...',              'she whispers, dropping her chin briefly before looking back up', 'T'),
            ('\"네가 좋아\"',                  'nega joa',                   'she admits softly, the words almost too quiet to catch', 'T'),
            ('\"여기 있을게\"',                'yeogi isseulge',             'she murmurs, settling back, unhurried', 'T'),
            ('\"네 생각만 했어\"',              'ne saenggakman haesseo',     'she admits, voice low, gaze drifting then returning', 'T'),
            ('\"천천히 봐도 돼\"',              'cheoncheonhi bwado dwae',    'she says quietly, her posture relaxed and open', 'T'),
            ('\"떠나지 마\"',                  'tteonaji ma',                'she breathes, the words slow and deliberate', 'T'),
            ('\"나만 봐\"',                    'naman bwa',                  'she says, barely above silence, eyes unblinking', 'T'),
            ('\"조금만 더\"',                  'jogeumman deo',              'she breathes, drawing out the last syllable', 'T'),
            # ── Sensual ───────────────────────────────────────────────────────
            ('\"이렇게 보는 거 좋아?\"',        'ireoke boneun geo joa?',     'she asks, voice low, eyes steady on the lens', 'S'),
            ('\"더 보여줄까?\"',               'deo boyeojulkka?',           'she says with quiet confidence, one shoulder dropping', 'S'),
            ('\"기분 좋지?\"',                 'gibun jochi?',               'she asks softly, tilting her chin up toward the camera', 'S'),
            ('\"만져도 돼\"',                   'manjyeo do dwae',            'she says quietly, guiding a hand toward her waist', 'S'),
            ('\"더 세게 해줘\"',               'deo sege haejwo',            'she breathes, pressing back into the touch', 'S'),
            ('\"느껴져?\"',                    'neukkyeojyeo?',              'she whispers, barely above silence, eyes holding the lens', 'S'),
            ('\"나 오늘 다 줄게\"',             'na oneul da julge',          'she says, voice low and deliberate', 'S'),
            ('\"이렇게 원했어\"',               'ireoke wonhaesseo',          'she admits, the words slow, gaze unwavering', 'S'),
            # ── Explicit ──────────────────────────────────────────────────────
            ('\"더 깊이, 제발\"',              'deo gip-i, jebal',           'she moans softly, hips tilting upward', 'X'),
            ('\"거기야, 멈추지 마\"',           'geogiya, meomchuji ma',      'she breathes urgently, fingers curling into the sheets', 'X'),
            ('\"나 갈 것 같아\"',              'na gal geot gata',           'she gasps, thighs pressing together', 'X'),
            ('\"다 삼켜줄게\"',               'da samkyeojulge',            'she says with quiet intensity, eyes direct', 'X'),
        ]

        _GRV_LINES_MANDARIN = [
            # ── Tasteful ──────────────────────────────────────────────────────
            ('\"好看吗?\"',                   'hǎo kàn ma?',                'she asks, voice barely above a breath, a faint smile at the corner of her mouth', 'T'),
            ('\"过来一点\"',                   'guòlái yīdiǎn',              'she says softly, drawing the words out', 'T'),
            ('\"我一直在想你\"',               'wǒ yīzhí zài xiǎng nǐ',     'she admits quietly, eyes dropping then lifting back to the lens', 'T'),
            ('\"不要走\"',                    'bù yào zǒu',                 'she breathes, the words slow and deliberate', 'T'),
            ('\"别这样看我嘛\"',               'bié zhèyàng kàn wǒ ma',     'she says, half-laughing, dropping her chin', 'T'),
            ('\"你让我脸红\"',                 'nǐ ràng wǒ liǎn hóng',      'she murmurs, touching her cheek lightly', 'T'),
            ('\"只给你看\"',                   'zhǐ gěi nǐ kàn',             'she says, barely audible, eyes steady on the camera', 'T'),
            ('\"你真的很坏\"',                 'nǐ zhēn de hěn huài',        'she says with a quiet laugh, shaking her head slowly', 'T'),
            ('\"慢慢来\"',                    'màn man lái',                'she breathes, the two words unhurried and deliberate', 'T'),
            ('\"看我\"',                      'kàn wǒ',                     'she murmurs, lifting her chin slowly toward the lens', 'T'),
            ('\"再多看一会儿\"',               'zài duō kàn yīhuìr',         'she says quietly, shifting her weight with unhurried ease', 'T'),
            # ── Sensual ───────────────────────────────────────────────────────
            ('\"你喜欢吗?\"',                  'nǐ xǐhuān ma?',              'she asks, tilting her head slightly, waiting', 'S'),
            ('\"我都给你看\"',                 'wǒ dōu gěi nǐ kàn',          'she breathes, the confidence in her voice soft but clear', 'S'),
            ('\"感觉好好\"',                   'gǎnjué hǎo hǎo',             'she exhales softly, eyes closing for a moment', 'S'),
            ('\"再靠近一点\"',                 'zài kàojìn yīdiǎn',          'she murmurs, the words trailing off into a soft breath', 'S'),
            ('\"你可以碰我\"',                 'nǐ kěyǐ pèng wǒ',            'she says quietly, shifting slightly toward the camera', 'S'),
            ('\"我想要你\"',                   'wǒ xiǎng yào nǐ',            'she breathes, the words barely above a whisper', 'S'),
            ('\"用力一点\"',                   'yòng lì yīdiǎn',             'she says softly, pressing back into the touch', 'S'),
            ('\"今晚我都是你的\"',              'jīn wǎn wǒ dōu shì nǐ de',  'she says, voice low and deliberate, gaze steady', 'S'),
            # ── Explicit ──────────────────────────────────────────────────────
            ('\"深一点，求你了\"',              'shēn yīdiǎn, qiú nǐ le',    'she moans softly, hips arching upward', 'X'),
            ('\"不要停，就在那里\"',            'bù yào tíng, jiù zài nà lǐ', 'she breathes urgently, fingers gripping tightly', 'X'),
            ('\"我要来了\"',                   'wǒ yào lái le',              'she gasps, thighs tensing around him', 'X'),
            ('\"全部吞下去\"',                 'quánbù tūn xià qù',          'she says with quiet intensity, eyes direct', 'X'),
        ]

        # ── Gravure singing pools — lyric fragments, not speech ───────────────
        # Used when _is_singing detected. Soft, melodic, intimate.
        _GRV_SINGING_JAPANESE = [
            ('「あなただけ… あなただけ…」',    'Anata dake... anata dake...',  'she sings in a low, breathy tone, the phrase dissolving into the air', 'T'),
            ('「夢の中で、あなたを待ってた」',  'Yume no naka de, anata wo matteta', 'she hums then shapes the words, eyes half-closed', 'T'),
            ('「もう離れないで、ねえ」',        'Mou hanarenaide, nee',        'she sings softly, drawing the last syllable into a lingering note', 'T'),
            ('「触れたくて、でも怖くて」',      'Furetakute, demo kowakute',   'she breathes the lyric more than sings it, voice catching slightly', 'T'),
            ('「あの夜のことを、忘れられない」', 'Ano yoru no koto wo, wasurerarenai', 'she sings, barely above a murmur, head bowing slowly', 'T'),
            ('「もっと、もっとそばにいて」',    'Motto, motto soba ni ite',    'she repeats the phrase twice, the second time softer than the first', 'T'),
            ('「体が熱くて、息ができない」',    'Karada ga atsukute, iki ga dekinai', 'she sings slowly, each word drawn out over a single soft note', 'S'),
            ('「好きだから、全部あげたい」',    'Suki dakara, zenbu agetai',   'she sings with quiet conviction, chin lifting slightly', 'S'),
            ('「感じてる、あなたを」',          'Kanjiteru, anata wo',         'she breathes the lyric into a held note, eyes closing', 'S'),
        ]
        _GRV_SINGING_KOREAN = [
            ('\"그대만을… 그대만을…\"',        'geudaemaneul... geudaemaneul...', 'she sings softly, the repetition fading on the second pass', 'T'),
            ('\"꿈속에서 너를 기다렸어\"',      'kkumsogeseo neoreul gidarysseo', 'she hums the melody first, then shapes the words quietly', 'T'),
            ('\"제발 떠나지 마, 응?\"',         'jebal tteonaji ma, eung?',    'she sings, drawing the final syllable into a gentle upward curve', 'T'),
            ('\"너무 보고 싶어서, 숨이 막혀\"', 'neomu bogo sipheoseo, sumi makhyeo', 'she sings barely above a whisper, hand resting at her chest', 'T'),
            ('\"몸이 뜨거워, 네 생각에\"',      'momi tteugeouo, ne saenggake', 'she sings slowly, the words lingering', 'S'),
            ('\"전부 줄게, 오늘 밤엔\"',        'jeonbu julge, oneul bamen',   'she sings with quiet conviction, chin tilting up', 'S'),
            ('\"느껴져, 너를\"',               'neukkyeojyeo, neoreul',       'she breathes into the note, eyes closing briefly', 'S'),
        ]
        _GRV_SINGING_MANDARIN = [
            ('\"只有你… 只有你…\"',            'zhǐ yǒu nǐ... zhǐ yǒu nǐ...', 'she sings softly, the phrase repeating and fading', 'T'),
            ('\"在梦里等着你\"',               'zài mèng lǐ děng zhe nǐ',    'she hums the melody before shaping the words quietly', 'T'),
            ('\"别离开我，好吗\"',              'bié líkāi wǒ, hǎo ma',       'she sings, the question trailing into a held note', 'T'),
            ('\"想你想到睡不着\"',              'xiǎng nǐ xiǎng dào shuì bù zháo', 'she sings barely above a whisper, chin dropping slightly', 'T'),
            ('\"身体很热，都是因为你\"',        'shēntǐ hěn rè, dōu shì yīnwèi nǐ', 'she sings slowly, each word drawn over a single quiet note', 'S'),
            ('\"今晚把我全给你\"',              'jīn wǎn bǎ wǒ quán gěi nǐ',  'she sings with soft conviction, gaze lifting to the lens', 'S'),
            ('\"感受着你\"',                   'gǎnshòu zhe nǐ',             'she breathes the lyric into a held note, eyes half-closing', 'S'),
        ]

        # ── Dialogue instruction ──────────────────────────────────────────────
        _user_quoted_lines = re.findall(r'["\u201c\u201d]([^"\u201c\u201d]+)["\u201c\u201d]', user_input)
        has_user_dialogue = bool(_user_quoted_lines)

        # Singing detection — swaps speech patterns for lyric fragments in gravure
        _is_singing = bool(re.search(
            r'\b(sing\w*|hum\w*|lullaby|lullabies|song|melody|croon\w*|chant\w*|serenade\w*|vocal\w*)\b',
            _combined_input, re.IGNORECASE
        ))

        # Scene-type signals for smarter general dialogue
        _is_tense    = bool(re.search(
            r'\b(interrogat|confront|argument|fight|threaten|demand|accus|suspect|detective|arrest|hostage)\b',
            _combined_input, re.IGNORECASE))
        _is_tender   = bool(re.search(
            r'\b(kiss|embrace|hold|comfort|cry|tears|gentle|tender|love|miss|goodbye|reunion)\b',
            _combined_input, re.IGNORECASE))
        _is_casual   = bool(re.search(
            r'\b(coffee|lunch|walk|park|street|shop|office|friend|chat|laugh|joke|conversation)\b',
            _combined_input, re.IGNORECASE))
        _is_athletic = bool(re.search(
            r'\b(run|sprint|train|gym|sport|fight|compete|race|climb|jump|push|lift weights)\b',
            _combined_input, re.IGNORECASE))

        if not has_person:
            dialogue_instruction = ""
        elif has_user_dialogue:
            # User supplied specific lines.
            # Language-aware: if gravure or explicit language request, translate rather than
            # deliver verbatim English — the meaning stays the same, the language changes.

            # Detect gravure language first (reuse same logic as invent_dialogue branch)
            _uq_grv_lang = None
            # "in english" anywhere in the input overrides gravure translation entirely
            _uq_english_override = bool(re.search(r'\bin\s+english\b', _combined_input, re.IGNORECASE))
            if is_gravure and not _uq_english_override:
                _uq_korean  = bool(re.search(r'\b(korean|korea)\b', _combined_input, re.IGNORECASE))
                _uq_chinese = bool(re.search(r'\b(chinese|china|mandarin|cantonese)\b', _combined_input, re.IGNORECASE))
                _uq_grv_lang = "Korean" if _uq_korean else "Mandarin" if _uq_chinese else "Japanese"
                _uq_roman = (
                    f"CRITICAL SCRIPT REQUIREMENT: You MUST write each line in full {('Korean (한국어)' if _uq_grv_lang == 'Korean' else 'Mandarin (中文)' if _uq_grv_lang == 'Mandarin' else 'Japanese (日本語)')} characters — "
                    f"kanji, hiragana, katakana, hangul, or hanzi as appropriate. "
                    f"Do NOT write romanisation only. Romanisation in parentheses comes AFTER the native script. "
                    f"Example format: 「もっと近くで見て」(Motto chikaku de mite) — NOT just the romanisation alone. "
                )

            # Detect explicit general language request
            _uq_explicit_lang_re = re.compile(
                r'\b(?:say(?:s|ing)?|speak(?:s|ing)?|shout(?:s|ing)?|whisper(?:s|ing)?|'
                r'mutter(?:s|ing)?|tell(?:s|ing)?|respond(?:s|ing)?|reply|replies|scream(?:s|ing)?|'
                r'calls?|cries?|cry(?:ing)?|grunt(?:s|ing)?|breath(?:es|ing)?|utter(?:s|ing)?|'
                r'exclaim(?:s|ing)?)\s+(?:\w+\s+){0,4}?in\s+(?:his|her|their|the)?\s*'
                r'(?:native\s+(?:language|tongue)|mother\s+tongue|'
                r'french|german|italian|spanish|portuguese|russian|arabic|hindi|thai|'
                r'vietnamese|indonesian|malay|tagalog|filipino|turkish|persian|farsi|'
                r'swedish|dutch|polish|greek|hebrew|ukrainian|czech|hungarian|romanian|'
                r'mandarin|cantonese|japanese|korean)\b'
                r'|\bin\s+(?:his|her|their|the)?\s*(?:native\s+(?:language|tongue)|mother\s+tongue)\b'
                r'|\bin\s+(?:french|german|italian|spanish|portuguese|russian|arabic|hindi|thai|'
                r'vietnamese|indonesian|malay|tagalog|filipino|turkish|persian|farsi|'
                r'swedish|dutch|polish|greek|hebrew|ukrainian|czech|hungarian|romanian|'
                r'mandarin|cantonese|japanese|korean)\b',
                re.IGNORECASE,
            )
            _uq_lang_match = _uq_explicit_lang_re.search(_combined_input)
            _uq_gen_lang = None
            if _uq_lang_match and not is_gravure:
                _uq_src = _uq_lang_match.group(0).lower()
                _UQ_LANG_MAP = {
                    "french": "French", "german": "German", "italian": "Italian",
                    "spanish": "Spanish", "portuguese": "Portuguese", "russian": "Russian",
                    "arabic": "Arabic", "hindi": "Hindi", "thai": "Thai",
                    "vietnamese": "Vietnamese", "indonesian": "Indonesian", "malay": "Malay",
                    "tagalog": "Filipino", "filipino": "Filipino", "turkish": "Turkish",
                    "persian": "Persian", "farsi": "Persian", "swedish": "Swedish",
                    "dutch": "Dutch", "polish": "Polish", "greek": "Greek",
                    "hebrew": "Hebrew", "ukrainian": "Ukrainian", "czech": "Czech",
                    "hungarian": "Hungarian", "romanian": "Romanian",
                    "mandarin": "Mandarin", "cantonese": "Cantonese",
                    "japanese": "Japanese", "korean": "Korean",
                }
                for key, val in _UQ_LANG_MAP.items():
                    if key in _uq_src:
                        _uq_gen_lang = val
                        break
                # "native language/tongue" with no specific language — infer from character
                if not _uq_gen_lang and ("native" in _uq_src or "mother" in _uq_src):
                    _uq_gen_lang = "their native language (infer from the character's nationality or ethnicity described in the scene)"

            _lines_formatted = "\n".join(
                f'{i+1}. "{line.strip()}"'
                for i, line in enumerate(_user_quoted_lines)
            )
            _invent_addendum = (
                "You may add invented dialogue between beats to fill the scene, "
                "but the required lines above take absolute priority. "
                if invent_dialogue else ""
            )

            if _uq_grv_lang:
                # Gravure — translate the user's lines into the correct language
                _uq_script_name = (
                    "kanji/hiragana/katakana" if _uq_grv_lang == "Japanese" else
                    "hangul (한글)" if _uq_grv_lang == "Korean" else
                    "hanzi (simplified Chinese characters)"
                )
                dialogue_instruction = (
                    f"\n\n[DIALOGUE INSTRUCTION — MANDATORY: "
                    f"The user has written {len(_user_quoted_lines)} line(s) of dialogue. "
                    f"Translate ALL of them into {_uq_grv_lang} and deliver IN ORDER. "
                    f"PRESERVE the exact meaning — do NOT substitute, paraphrase, or invent different content. "
                    f"SCRIPT REQUIREMENT: Write in actual {_uq_script_name} characters — NOT romanisation only. "
                    f"PARENTHESES ARE FORBIDDEN: do NOT write romanisation in parentheses next to the dialogue — "
                    f"it renders as on-screen subtitles in the video. "
                    f"Write the native script characters only — inline in the prose, no brackets alongside. "
                    f"CORRECT: She whispers 「もっと近くで見て」, voice barely above silence. "
                    f"WRONG: She whispers 「もっと近くで見て」(Motto chikaku de mite). "
                    f"Each line is woven into a physical beat with acting direction.\n"
                    f"LINES TO TRANSLATE IN ORDER:\n{_lines_formatted}\n"
                    f"{_invent_addendum}"
                    f"Never use [DIALOGUE: ...] tags.]"
                )
            elif _uq_gen_lang:
                # General explicit language request — translate those specific lines
                _NON_LATIN = ("Japanese", "Korean", "Mandarin", "Cantonese",
                               "Arabic", "Hindi", "Thai", "Persian", "Russian",
                               "Greek", "Hebrew", "Ukrainian")
                if _uq_gen_lang in _NON_LATIN:
                    _uq_script_map = {
                        "Japanese": "kanji/hiragana/katakana",
                        "Korean": "hangul (한글)", "Mandarin": "hanzi (simplified)",
                        "Cantonese": "hanzi (traditional)", "Arabic": "Arabic script (العربية)",
                        "Hindi": "Devanagari (देवनागरी)", "Thai": "Thai script (ภาษาไทย)",
                        "Persian": "Persian script (فارسی)", "Russian": "Cyrillic (кириллица)",
                        "Greek": "Greek script (ελληνικά)", "Hebrew": "Hebrew script (עברית)",
                        "Ukrainian": "Cyrillic (кирилиця)",
                    }
                    _uq_roman_note = (
                        f"Write in actual {_uq_script_map.get(_uq_gen_lang, _uq_gen_lang + ' script')} — NOT romanisation only. "
                        f"Format: native script first, then romanisation in parentheses for pronunciation only. "
                        f"The parentheses contain pronunciation ONLY — NOT an English translation. "
                        f"Example for Russian: «Где ты?» (Gde ty?) — correct. "
                        f"«Где ты?» (Where are you?) — WRONG, that is a translation not pronunciation. "
                    )
                else:
                    _uq_roman_note = (
                        f"Write in {_uq_gen_lang} only — no romanisation needed. "
                    )
                dialogue_instruction = (
                    f"\n\n[DIALOGUE INSTRUCTION — MANDATORY: "
                    f"The user has written {len(_user_quoted_lines)} line(s) of dialogue. "
                    f"Translate ALL of them into {_uq_gen_lang} and deliver IN ORDER. "
                    f"PRESERVE the exact meaning — do NOT substitute or invent different content. "
                    f"{_uq_roman_note}"
                    f"Each line is woven into a physical beat with acting direction.\n"
                    f"LINES TO TRANSLATE IN ORDER:\n{_lines_formatted}\n"
                    f"{_invent_addendum}"
                    f"Never use [DIALOGUE: ...] tags.]"
                )
            else:
                # No language request — deliver verbatim as before
                dialogue_instruction = (
                    f"\n\n[DIALOGUE INSTRUCTION — MANDATORY AND VERBATIM: "
                    f"The user has written {len(_user_quoted_lines)} specific line(s) of dialogue. "
                    f"You MUST deliver ALL of them, IN ORDER, word-for-word. "
                    f"Do NOT paraphrase, skip, or merge any line. "
                    f"Do NOT describe the effect of speaking instead of writing the actual words. "
                    f"Each line must appear in quotes in the output, "
                    f"with a physical acting direction between each line.\n"
                    f"REQUIRED LINES IN ORDER:\n{_lines_formatted}\n"
                    f"{_invent_addendum}"
                    f"Never use [DIALOGUE: ...] tags.]"
                )
        elif invent_dialogue:
            if is_gravure:
                # ── Language resolver — ethnicity/nationality → language ────────
                # Priority: explicit language keyword > nationality > ethnicity > default (Japanese)
                # Pools exist for Japanese/Korean/Mandarin.
                # All other languages use LLM-generated dialogue with structural guidance.
                def _detect_grv_language(text):
                    t = text.lower()
                    if re.search(r'\b(japanese|japan)\b', t):        return "Japanese"
                    if re.search(r'\b(korean|korea)\b', t):           return "Korean"
                    if re.search(r'\b(chinese|china|mandarin|cantonese)\b', t): return "Mandarin"
                    if re.search(r'\b(french|france|parisian)\b', t): return "French"
                    if re.search(r'\b(german|germany|deutsch)\b', t): return "German"
                    if re.search(r'\b(italian|italy)\b', t):          return "Italian"
                    if re.search(r'\b(spanish|spain|latina|mexican|colombian|argentinian)\b', t): return "Spanish"
                    if re.search(r'\b(portuguese|portugal|brazilian)\b', t): return "Portuguese"
                    if re.search(r'\b(russian|russia)\b', t):         return "Russian"
                    if re.search(r'\b(arabic|arab|lebanese|moroccan|egyptian|saudi|emirati|gulf)\b', t): return "Arabic"
                    if re.search(r'\b(hindi|indian|south asian|bengali|punjabi)\b', t): return "Hindi"
                    if re.search(r'\b(thai|thailand)\b', t):          return "Thai"
                    if re.search(r'\b(vietnamese|vietnam)\b', t):     return "Vietnamese"
                    if re.search(r'\b(indonesian|indonesia|malay|malaysia)\b', t): return "Indonesian"
                    if re.search(r'\b(tagalog|filipino|philippines)\b', t): return "Filipino"
                    if re.search(r'\b(turkish|turkey)\b', t):         return "Turkish"
                    if re.search(r'\b(persian|iranian|farsi|iran)\b', t): return "Persian"
                    if re.search(r'\b(swedish|sweden)\b', t):         return "Swedish"
                    if re.search(r'\b(dutch|netherlands|holland)\b', t): return "Dutch"
                    if re.search(r'\b(polish|poland)\b', t):          return "Polish"
                    if re.search(r'\b(greek|greece)\b', t):           return "Greek"
                    if re.search(r'\b(east asian)\b', t):             return "Japanese"
                    return "Japanese"  # gravure default

                _grv_lang    = _detect_grv_language(_combined_input)
                _has_pool    = _grv_lang in ("Japanese", "Korean", "Mandarin")
                _speech_pool = (
                    _GRV_LINES_JAPANESE if _grv_lang == "Japanese" else
                    _GRV_LINES_KOREAN   if _grv_lang == "Korean"   else
                    _GRV_LINES_MANDARIN if _grv_lang == "Mandarin"  else []
                )
                _sing_pool = (
                    _GRV_SINGING_JAPANESE if _grv_lang == "Japanese" else
                    _GRV_SINGING_KOREAN   if _grv_lang == "Korean"   else
                    _GRV_SINGING_MANDARIN if _grv_lang == "Mandarin"  else []
                )
                # Script requirement — native characters inline in prose, NO parenthetical romanisation
                _roman_note = (
                    f"CRITICAL SCRIPT AND FORMAT REQUIREMENT: "
                    f"Write each line in full {_grv_lang} characters "
                    f"({'kanji/hiragana/katakana' if _grv_lang == 'Japanese' else 'hangul (한글)' if _grv_lang == 'Korean' else 'hanzi/simplified Chinese'}). "
                    f"Do NOT write romanisation only, and do NOT put romanisation in parentheses next to the dialogue — "
                    f"parenthetical text renders as on-screen subtitles in the video. "
                    f"CORRECT: She whispers 「もっと近くで見て」, the syllables drawn out softly. "
                    f"WRONG: She whispers 「もっと近くで見て」(Motto chikaku de mite). "
                    f"Write native script characters only — no brackets, no romanisation alongside. "
                )

                # Seed-driven RNG for reproducible variety
                _dlg_rng = random.Random(seed if seed != -1 else None)

                if _is_singing:
                    # ── Singing mode ──────────────────────────────────────────
                    if _has_pool:
                        _sing_tier = [l for l in _sing_pool if l[3] in ('T', 'S')] if not is_explicit else _sing_pool
                        _sing_picked = _dlg_rng.sample(_sing_tier, min(3, len(_sing_tier)))
                        _sing_examples = "  ".join(
                            f"'{script} ({roman}) — {note}.'"
                            for script, roman, note, _ in _sing_picked
                        )
                        _sing_example_line = (
                            f"EXAMPLE TONE AND FORMAT (do NOT copy verbatim — invent your own lyric content): {_sing_examples} "
                        )
                    else:
                        _sing_example_line = (
                            f"EXAMPLE FORMAT: 'Tu sei tutto per me... (she sings, barely above a breath, "
                            f"the phrase dissolving on the last syllable)' — adapt this structure to {_grv_lang}. "
                        )
                    dialogue_instruction = (
                        "\n\n[VOCAL/SINGING INSTRUCTION — MANDATORY, CANNOT BE SKIPPED: "
                        f"She sings or hums ONLY in {_grv_lang}. No English lyrics. "
                        "Use lyric-style fragments — short melodic phrases, not full sentences of speech. "
                        "Include THREE vocal moments: one early (establishing the melody), "
                        "one mid (emotionally peaks), one late (fades or resolves). "
                        "Describe HOW she sings each line — breath, volume, note shape, where the phrase dissolves. "
                        "Lyrics should feel written for intimacy — soft, personal, slightly incomplete, "
                        "as if she is singing to one person only. "
                        + _roman_note
                        + _sing_example_line
                        + music_sound_rule + "]"
                    )
                else:
                    # ── Speech mode ───────────────────────────────────────────
                    # Tier-specific tone brief
                    if is_explicit:
                        _grv_tone = (
                            "Lines range across the scene: one can be playful or teasing, "
                            "one intimate and confessional, one direct and physically explicit. "
                            "Explicit lines should be raw and specific — match exactly what is happening in the scene. "
                            "Do NOT sanitise or euphemise if the scene is explicit."
                        )
                    elif is_sensual:
                        _grv_tone = (
                            "Lines span the emotional range of the scene: one playful or curious, "
                            "one intimate and slightly vulnerable, one sensual and direct. "
                            "Stay at the level of sensuality the scene describes — do not self-escalate."
                        )
                    else:
                        _grv_tone = (
                            "Lines are warm, intimate, and camera-aware: one playful, "
                            "one confessional or emotionally open, one direct and present. "
                            "Keep all content tasteful — no explicit or overtly sexual language."
                        )

                    if _has_pool:
                        # Pool languages — use tiered examples + LLM invents third
                        if is_explicit:
                            _active_pool = _speech_pool
                        elif is_sensual:
                            _active_pool = [l for l in _speech_pool if l[3] in ('T', 'S')]
                        else:
                            _active_pool = [l for l in _speech_pool if l[3] == 'T']
                        if len(_active_pool) < 3:
                            _active_pool = [l for l in _speech_pool if l[3] in ('T', 'S')]
                        if len(_active_pool) < 3:
                            _active_pool = _speech_pool

                        _picked = _dlg_rng.sample(_active_pool, min(2, len(_active_pool)))
                        _grv_examples = "  ".join(
                            f"'{script} ({roman}), {note}.'"
                            for script, roman, note, _ in _picked
                        )
                        _example_line = (
                            "ANCHOR EXAMPLES — use these two as style/register reference, "
                            f"then INVENT a third line yourself in the same language and register: {_grv_examples} "
                        )
                    else:
                        # Non-pool language — LLM writes all three lines itself
                        # Give it a structural example in the target language style
                        _example_line = (
                            f"INVENT all three lines yourself in natural, fluent {_grv_lang}. "
                            "Lines must sound authentic and idiomatic — not translated from English. "
                            "Use vocabulary and phrasing that fits the intimate, camera-aware register of this scene. "
                        )

                    dialogue_instruction = (
                        "\n\n[DIALOGUE INSTRUCTION — MANDATORY, CANNOT BE SKIPPED: "
                        f"She speaks ONLY in {_grv_lang}. Do NOT write English dialogue. "
                        "Include THREE spoken moments — one early in the scene, one mid, one late. "
                        "Each is a COMPLETE PHRASE or short sentence — never a single word. "
                        + _grv_tone + " "
                        + _roman_note
                        + "Weave each line into a physical beat — a movement, a shift of weight, a held gaze. "
                        "Voice always soft and intimate — never loud or rushed. "
                        + _example_line
                        + music_sound_rule + "]"
                    )
            else:
                # ── General scene ─────────────────────────────────────────────
                # Detect if user explicitly requested a specific language for dialogue.
                # Only fires on direct user instruction — "in French", "in German",
                # "in her native language/tongue", "says in Spanish" etc.
                # Does NOT fire just because a nationality is mentioned.
                _EXPLICIT_LANG_REQUEST_RE = re.compile(
                    r'\b(?:say(?:s|ing)?|speak(?:s|ing)?|shout(?:s|ing)?|whisper(?:s|ing)?|'
                    r'mutter(?:s|ing)?|tell(?:s|ing)?|respond(?:s|ing)?|reply|replies|scream(?:s|ing)?|'
                    r'calls?|cries?|cry(?:ing)?|grunt(?:s|ing)?|breath(?:es|ing)?|utter(?:s|ing)?|'
                    r'exclaim(?:s|ing)?)\s+(?:\w+\s+){0,4}?in\s+(?:his|her|their|the)?\s*'
                    r'(?:native\s+(?:language|tongue)|mother\s+tongue|'
                    r'french|german|italian|spanish|portuguese|russian|arabic|hindi|thai|'
                    r'vietnamese|indonesian|malay|tagalog|filipino|turkish|persian|farsi|'
                    r'swedish|dutch|polish|greek|hebrew|ukrainian|czech|hungarian|romanian|'
                    r'mandarin|cantonese|japanese|korean)\b'
                    r'|'
                    r'\bin\s+(?:his|her|their|the)?\s*(?:native\s+(?:language|tongue)|mother\s+tongue)\b',
                    re.IGNORECASE,
                )
                _lang_request_match = _EXPLICIT_LANG_REQUEST_RE.search(_combined_input)

                # Also detect a bare "in [language]" phrasing close to a dialogue verb
                # e.g. "an angry German man says in German" or "she whispers in French"
                _BARE_LANG_RE = re.compile(
                    r'\bin\s+(french|german|italian|spanish|portuguese|russian|arabic|hindi|thai|'
                    r'vietnamese|indonesian|malay|tagalog|filipino|turkish|persian|farsi|'
                    r'swedish|dutch|polish|greek|hebrew|ukrainian|czech|hungarian|romanian|'
                    r'mandarin|cantonese|japanese|korean)\b',
                    re.IGNORECASE,
                )
                _bare_lang_match = _BARE_LANG_RE.search(_combined_input)

                # Resolve requested language name
                _requested_lang = None
                if _lang_request_match or _bare_lang_match:
                    _src = (_lang_request_match or _bare_lang_match).group(0).lower()
                    _LANG_NAME_MAP = {
                        "french": "French", "german": "German", "italian": "Italian",
                        "spanish": "Spanish", "portuguese": "Portuguese", "russian": "Russian",
                        "arabic": "Arabic", "hindi": "Hindi", "thai": "Thai",
                        "vietnamese": "Vietnamese", "indonesian": "Indonesian", "malay": "Malay",
                        "tagalog": "Filipino", "filipino": "Filipino", "turkish": "Turkish",
                        "persian": "Persian", "farsi": "Persian", "swedish": "Swedish",
                        "dutch": "Dutch", "polish": "Polish", "greek": "Greek",
                        "hebrew": "Hebrew", "ukrainian": "Ukrainian", "czech": "Czech",
                        "hungarian": "Hungarian", "romanian": "Romanian",
                        "mandarin": "Mandarin", "cantonese": "Cantonese",
                        "japanese": "Japanese", "korean": "Korean",
                    }
                    for key, val in _LANG_NAME_MAP.items():
                        if key in _src:
                            _requested_lang = val
                            break
                    # "native language/tongue" — no specific language named, infer from character
                    if not _requested_lang and ("native" in _src or "mother" in _src):
                        _requested_lang = "_infer"

                # Romanisation note for non-Latin script languages
                _NON_LATIN_SCRIPTS = {
                    "Japanese":  "Japanese characters (kanji/hiragana/katakana)",
                    "Korean":    "Korean hangul characters (한글)",
                    "Mandarin":  "Chinese characters (hanzi/simplified)",
                    "Cantonese": "Chinese characters (traditional/simplified)",
                    "Arabic":    "Arabic script (العربية)",
                    "Hindi":     "Devanagari script (देवनागरी)",
                    "Thai":      "Thai script (ภาษาไทย)",
                    "Persian":   "Persian/Farsi script (فارسی)",
                    "Russian":   "Cyrillic script (кириллица)",
                    "Greek":     "Greek script (ελληνικά)",
                    "Hebrew":    "Hebrew script (עברית)",
                    "Ukrainian": "Cyrillic script (кирилиця)",
                }
                _gen_roman_note = ""
                if _requested_lang in _NON_LATIN_SCRIPTS:
                    _script_name = _NON_LATIN_SCRIPTS[_requested_lang]
                    _gen_roman_note = (
                        f"CRITICAL: Write the dialogue in actual {_script_name} — NOT romanisation only. "
                        f"Do NOT put romanisation in parentheses next to the dialogue — parenthetical text "
                        f"renders as on-screen subtitles in the video. Write native script characters only, "
                        f"inline in the prose with no brackets alongside. "
                        f"CORRECT: She whispers «Где ты?», voice low and urgent. "
                        f"WRONG: She whispers «Где ты?» (Gde ty?). "
                    )
                elif _requested_lang and _requested_lang != "_infer":
                    _gen_roman_note = (
                        f"Write the {_requested_lang} dialogue in the native language only — "
                        f"no romanisation needed. "
                    )
                elif _requested_lang == "_infer":
                    _gen_roman_note = (
                        "If the character's native language uses a non-Latin script, write native script "
                        "characters only — no romanisation in parentheses as this renders as on-screen subtitles. "
                        "If it uses a Latin script, write the native language only with no romanisation. "
                    )

                # Language addendum — only appended when user explicitly requested it
                if _requested_lang == "_infer":
                    _lang_addendum = (
                        "\nLANGUAGE NOTE: The user has asked for dialogue in the character's native language. "
                        "Identify the character's nationality or ethnicity from the scene description "
                        "and write the relevant dialogue in that language. "
                        "If no clear nationality is stated, use the language most consistent with the scene's context. "
                        + _gen_roman_note
                    )
                elif _requested_lang:
                    _lang_addendum = (
                        f"\nLANGUAGE NOTE: The user has asked for dialogue in {_requested_lang}. "
                        f"Write those specific lines in {_requested_lang} exactly as requested. "
                        f"Other dialogue in the scene (if any) can remain in English. "
                        + _gen_roman_note
                    )
                else:
                    _lang_addendum = ""

                # Scene-type tone brief
                if _is_tense:
                    _dlg_tone = (
                        "Dialogue is clipped and charged — short sentences, pressure in every word. "
                        "Characters don't finish each other's sentences. Silences between lines are loaded. "
                        "Example register: '\"Sit down,\" he says, voice flat.' "
                        "or '\"I didn't say you could leave.\" He steps closer.'")
                elif _is_tender:
                    _dlg_tone = (
                        "Dialogue is soft, unguarded, and emotionally specific — the kind of thing "
                        "people only say when they mean it. No performance, no deflection. "
                        "Example register: '\"I thought I'd lost you,\" she says, barely audible.' "
                        "or '\"You don't have to explain,\" he murmurs, hand finding her shoulder.'")
                elif _is_athletic:
                    _dlg_tone = (
                        "Dialogue is sparse and physical — short commands, exertion sounds, brief focus cues. "
                        "Words land between breaths. "
                        "Example register: '\"Again,\" he says, jaw tight.' "
                        "or '\"Come on,\" she mutters through clenched teeth, pushing through the burn.'")
                elif is_explicit or is_sensual:
                    _dlg_tone = (
                        "Dialogue is direct and physical, grounded in what is happening in the scene. "
                        "Lines are short, urgent, or breathless — no literary flourish. "
                        "Example register: '\"Don\\'t stop,\" she breathes, fingers tightening.' "
                        "or '\"Look at me,\" he says quietly, slowing his pace deliberately.'")
                elif _is_casual:
                    _dlg_tone = (
                        "Dialogue sounds like real conversation — unpolished, natural, with the kind of "
                        "half-sentences and overlaps that real people use. "
                        "Example register: '\"Sorry, I — did you want the last one?\" she asks, already reaching.' "
                        "or '\"No, I get it,\" he says, though his expression says otherwise.'")
                else:
                    _dlg_tone = (
                        "Dialogue is specific to this exact moment — what would this person actually say "
                        "right now, in this situation, with this level of emotion? "
                        "No generic lines. Ground every word in what is physically happening.")

                dialogue_instruction = (
                    "\n\n[DIALOGUE INSTRUCTION — MANDATORY, CANNOT BE SKIPPED: "
                    "Include at least TWO lines of spoken dialogue, spaced across the scene — not dumped in one block. "
                    "Each line is woven into a physical beat with attribution and a delivery note. "
                    "Lines must vary in register or emotional weight — do NOT write two lines of the same tone. "
                    "Do NOT write generic filler ('\"Wow\"', '\"OK\"', '\"Yeah\"' alone). "
                    "Every line must reveal character, intention, or emotional state. "
                    + _dlg_tone + " "
                    "Invented dialogue MUST be grounded in what is visibly happening — "
                    "do NOT invent backstory or context not in the user's input. "
                    + _lang_addendum
                    + music_sound_rule + "]"
                )
        else:
            dialogue_instruction = (
                "\n\n[DIALOGUE INSTRUCTION: No dialogue in this scene. No spoken words. "
                "Weave sound naturally into the prose instead. "
                + music_sound_rule + "]"
            )

        # ── Lift instruction ──────────────────────────────────────────────────
        if has_lift:
            # Detect which garment is being lifted to write the correct steps
            _lift_garment_match = re.search(
                r'\b(skirt|dress)\b', _combined_input, re.IGNORECASE
            )
            if _lift_garment_match:
                _lift_garment = _lift_garment_match.group(1).lower()
                lift_instruction = (
                    f"\n\n[{_lift_garment.upper()} LIFT SEQUENCE — MANDATORY, one sentence per step: "
                    f"1. Her fingers grip the hem of her {_lift_garment} at mid-thigh. "
                    f"2. She gathers the fabric upward. "
                    f"3. The {_lift_garment} rises past mid-thigh. "
                    f"4. The fabric clears her upper thighs. "
                    f"5. Her hips and underwear/skin come into view. "
                    f"6. The {_lift_garment} is held bunched at her waist. "
                    f"The {_lift_garment} STAYS LIFTED. Do NOT write her lowering it or covering herself unless asked.]"
                )
            else:
                # Default: shirt/top/crop lift → chest reveal
                lift_instruction = (
                    "\n\n[SHIRT LIFT SEQUENCE — MANDATORY, one sentence per step: "
                    "1. Her fingers find the hem at the waist. "
                    "2. She grips the fabric and begins gathering it upward. "
                    "3. The shirt rises past her stomach. "
                    "4. The fabric passes her navel, exposing her bare midriff. "
                    "5. The shirt climbs past her ribs. "
                    "6. Her chest comes into view. "
                    "7. Her breasts are fully exposed, the shirt held up. "
                    "The shirt STAYS LIFTED. Do NOT write her lowering it or covering herself unless asked.]"
                )
        else:
            lift_instruction = ""

        # ── Character seed ────────────────────────────────────────────────────
        # Detect whether the user has described physical appearance (age, hair, skin, build, clothing).
        # Role words (man, woman, detective, suspect etc.) deliberately excluded here —
        # those trigger has_person and multi detection but do NOT count as a character description.
        # Without a physical description the char seed should still fire for single-person scenes,
        # and multi_instruction should still fire for two-person scenes.
        # Suppresses char seed if user has anchored the scene with ANY person reference
        # or appearance/clothing detail. The rule: if the user told us who is there,
        # we do not overwrite them with a random blueprint.
        # Also suppresses when the scene is defined by a non-human subject (animal, creature,
        # vehicle, object) so we don't paste a random character onto a gorilla close-up.
        _scene_is_anchored        = bool(self._NON_HUMAN_RE.search(user_input))
        _user_described_character = _scene_is_anchored or bool(self._USER_CHAR_RE.search(user_input))

        # ── Gender detection ──────────────────────────────────────────────────
        # Reads user_input for explicit gender signals so the char seed matches.
        # "neutral" = no signal found → seed picks randomly.
        _has_male   = bool(self._MALE_RE.search(user_input))
        _has_female = bool(self._FEMALE_RE.search(user_input))

        if _has_male and not _has_female:
            _gender = "male"
        elif _has_female and not _has_male:
            _gender = "female"
        else:
            # Both signals or neither — let the seed decide randomly
            _gender = "neutral"

        print(f"[LTX2-Qwen] Gender signal: {_gender} (male={_has_male}, female={_has_female})")

        # Use _active_scene_context (respects use_scene_context flag)
        is_multi    = bool(self._MULTI_RE.search(user_input + " " + _active_scene_context))
        # Explicit subject_count overrides text-based multi detection
        if subject_count and subject_count > 0:
            is_multi = subject_count > 1

        if has_person and not _user_described_character and not is_gravure:
            rng = random.Random(seed if seed != -1 else None)
            if is_multi:
                # Two-person scene — generate two distinct seeds so the LLM has both characters.
                # For mixed-signal scenes (e.g. "detective and suspect" with no gender) we let
                # each seed pick independently so we get variety.
                char_a = _build_char_seed(rng, adult_only=(is_sensual or is_explicit), gender=_gender)
                # Second person always neutral so a mixed-gender pair is possible
                char_b = _build_char_seed(rng, adult_only=(is_sensual or is_explicit), gender="neutral")
                char_seed_note = (
                    f"\n[CHARACTER SUGGESTIONS — TWO PEOPLE (only if the scene does not already define them): "
                    f"Person A: {char_a}. "
                    f"Person B: {char_b}. "
                    f"These are loose suggestions — if the scene implies specific people, ignore this entirely. "
                    f"If used, give each person clothing appropriate to the scene. "
                    f"Establish both spatially — left/right or foreground/background — and keep descriptors consistent.]"
                )
            else:
                char_description = _build_char_seed(rng, adult_only=(is_sensual or is_explicit), gender=_gender)
                char_seed_note = (
                    f"\n[CHARACTER SUGGESTION (only if no character is defined by the scene above): {char_description}. "
                    f"This is a loose suggestion only — if the scene already implies a specific person, ignore this entirely. "
                    f"If used, add clothing appropriate to the scene context.]"
                )
        else:
            char_seed_note = ""
            if has_person and _user_described_character:
                print("[LTX2-Qwen] User described character — seed suppressed.")
            elif is_gravure and not _user_described_character:
                print("[LTX2-Qwen] Gravure preset — char seed suppressed, preset defines character.")

        # ── Gravure body override ─────────────────────────────────────────────
        # If the user specified a body type, inject it as a hard override so the
        # gravure preset's default "petite to medium build" doesn't silently win.
        _gravure_body_override = ""
        if is_gravure:
            _body_matches = list(dict.fromkeys(
                m.group(0).lower() for m in self._BODY_STYLE_RE.finditer(user_input)
            ))
            if _body_matches:
                _body_str = ", ".join(_body_matches)
                _gravure_body_override = (
                    f"\n[GRAVURE BODY OVERRIDE — MANDATORY: The user has described the body type as: "
                    f"{_body_str}. Use this EXACTLY. Ignore the preset's default build description. "
                    f"The body type stated by the user is the ceiling and the floor — do not soften, "
                    f"expand, or substitute it.]"
                )

        # ── Vision context ────────────────────────────────────────────────────
        if _active_scene_context and _active_scene_context.strip():
            effective_input = (
                f"[SCENE CONTEXT FROM IMAGE — ABSOLUTE AUTHORITY: "
                f"This is what is actually in the image. Every visual detail here is ground truth. "
                f"Do NOT invent, replace, or contradict any aspect of this description — "
                f"clothing, skin tone, hair, body type, setting, or lighting. "
                f"Any CHARACTER SEED instruction below does NOT apply when an image is provided; disregard it entirely.]\n"
                f"{_active_scene_context.strip()}\n\n"
                f"[USER DIRECTION — apply this as action, style, and mood layered over the above scene. "
                f"The subject looks exactly as described in the image context above. Do not change their appearance.]\n"
                f"{user_input.strip()}"
            )
        else:
            effective_input = user_input.strip()
            if has_person and _user_described_character:
                effective_input += (
                    "\n[CHARACTER NOTE: The user has described the character's appearance. "
                    "Use ONLY the user's description for all visual details. "
                    "Do NOT invent or substitute any appearance detail not present in the input above.]"
                )
            effective_input += char_seed_note

        # ── LoRA triggers ─────────────────────────────────────────────────────
        if lora_triggers and lora_triggers.strip():
            lora_instruction = (
                f"\n[LORA NOTE: LoRA trigger words will be prepended automatically. "
                f"Do NOT include them in your output. Start directly with the style label or scene description.]"
            )
        else:
            lora_instruction = ""

        # ── Pacing instruction ────────────────────────────────────────────────
        length_instruction = (
            f"\n[PACING: {pacing_hint} "
            f"HARD WORD LIMIT: {token_val} words maximum — do not exceed this. "
            f"Do not exceed the action count above. "
            f"Output ends with the final sentence of the scene — no summaries, no counts, no closings, no meta-commentary, no brackets after the last word.]"
        )

        # ── Build messages ────────────────────────────────────────────────────
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user",   "content": (
                effective_input
                + lora_instruction
                + orientation_instruction
                + _ratio_instruction
                + _subject_count_instruction
                + _camera_lock_instruction
                + _negative_bias_instruction
                + _audio_instruction
                + style_instruction
                + portrait_instruction
                + _gravure_body_override
                + sequence_instruction
                + static_instruction
                + no_person_instruction
                + multi_instruction
                + dialogue_instruction
                + explicit_instruction
                + lift_instruction
                + length_instruction
            )},
        ]

        # ── Tokenise ──────────────────────────────────────────────────────────
        try:
            raw = self.tokenizer.apply_chat_template(
                messages, return_tensors="pt",
                add_generation_prompt=True, enable_thinking=False,
            )
        except TypeError:
            # enable_thinking not supported by this tokenizer version — retry without it
            print("[LTX2-Qwen] enable_thinking kwarg not supported — retrying without it")
            raw = self.tokenizer.apply_chat_template(
                messages, return_tensors="pt",
                add_generation_prompt=True,
            )
        if hasattr(raw, "input_ids"):
            input_ids = raw.input_ids.to(self.model.device)
        elif isinstance(raw, dict):
            input_ids = raw["input_ids"].to(self.model.device)
        elif isinstance(raw, list):
            input_ids = torch.tensor([raw], dtype=torch.long).to(self.model.device)
        else:
            input_ids = raw.to(self.model.device)
        input_length = input_ids.shape[1]

        # ── Generate ──────────────────────────────────────────────────────────
        try:
            with torch.no_grad():
                output_ids = self.model.generate(
                    input_ids,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=True,
                    top_k=20,
                    top_p=0.82,
                    min_p=0.0,
                    repetition_penalty=1.05,
                    use_cache=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self._stop_token_ids,
                )
        except Exception as e:
            print(f"[LTX2-Qwen] Generation error: {e}")
            self.unload_model()
            raise

        result = self.tokenizer.decode(output_ids[0][input_length:], skip_special_tokens=True).strip()
        del output_ids, input_ids
        gc.collect()

        if not result or not result.strip():
            print("[LTX2-Qwen] Warning: empty generation — returning user input as fallback")
            result = user_input.strip()

        result = self._clean_output(result)

        # ── Hard word-count truncation ────────────────────────────────────────
        cap   = int(token_val * 1.05)
        words = result.split()
        if len(words) > cap:
            trunc = " ".join(words[:cap])
            # Find the last sentence-ending punctuation in the truncated text.
            # Require it to be past 40% of the string so we don't cut too early.
            # If no clean sentence boundary exists, strip trailing partial clause
            # punctuation (comma, semicolon, colon, em-dash) and close with a period.
            best = max((trunc.rfind(c) for c in ".!?"), default=-1)
            if best > int(len(trunc) * 0.4):
                result = trunc[:best + 1].strip()
            else:
                result = trunc.rstrip(",;:— ").strip()
                if result and result[-1] not in ".!?":
                    result += "."
            print(f"[LTX2-Qwen] Truncated: {len(words)} → {len(result.split())} words")

        # ── LoRA trigger hard prepend ─────────────────────────────────────────
        if lora_triggers and lora_triggers.strip():
            triggers = lora_triggers.strip()
            if result.lower().startswith(triggers.lower()):
                result = result[len(triggers):].lstrip(" ,—-")
            result = triggers + ", " + result
            print(f"[LTX2-Qwen] LoRA triggers prepended: {triggers}")

        # ── Style label safety net ────────────────────────────────────────────
        if style_label:
            # Strip a leading duplicate if the LLM already emitted the label
            # (handles cases where the label appears twice at the start).
            _label_lower  = style_label.lower().rstrip(". ")
            _result_lower = result.lower().lstrip()
            if _result_lower.startswith(_label_lower):
                # Label present once — strip it so we can re-prepend cleanly below
                result = result[len(style_label):].lstrip(" .,")
                _result_lower = result.lower().lstrip()
            # Now check if the stripped result still starts with the label (double print)
            # and strip again if so
            if _result_lower.startswith(_label_lower):
                result = result[len(style_label):].lstrip(" .,")
            # Always prepend the canonical label
            result = style_label + " " + result.lstrip()
            print(f"[LTX2-Qwen] Style label applied: {style_label}")

        # ── Negative prompt ───────────────────────────────────────────────────
        neg = _build_negative_prompt(result, user_input, is_portrait=is_portrait, style_preset=style_preset)
        if negative_bias and negative_bias.strip():
            neg = neg + ", " + negative_bias.strip()

        # ── Always offload — every run, no exceptions ─────────────────────────
        # keep_model_loaded widget is retained in the UI for legacy compatibility
        # but the node always offloads so VRAM is fully freed before LTX runs.
        self.unload_model()

        print(f"[LTX2-Qwen] Done — {len(result.split())} words")
        return (result, result, neg)


# ── Utility: manual unload node ───────────────────────────────────────────────

class LTX2UnloadModelQwen:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {}}
    RETURN_TYPES = ()
    FUNCTION     = "unload"
    CATEGORY     = "LTX2"
    OUTPUT_NODE  = True

    def unload(self):
        freed = 0
        for obj in gc.get_objects():
            if isinstance(obj, LTX2PromptArchitectQwen) and obj.model is not None:
                obj.unload_model()
                freed += 1
        print(f"[LTX2-Qwen] Unload node: freed {freed} instance(s).")
        return ()


# ── ComfyUI registration ──────────────────────────────────────────────────────

NODE_CLASS_MAPPINGS = {
    "LTX2PromptArchitectQwen": LTX2PromptArchitectQwen,
    "LTX2UnloadModelQwen":     LTX2UnloadModelQwen,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LTX2PromptArchitectQwen": "LTX-2.3 Easy Prompt Qwen By LoRa-Daddy",
    "LTX2UnloadModelQwen":     "LTX2 Unload Model (Qwen)",
}
