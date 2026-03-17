import re
import os
import json
import random
import time as _time

# ── HuggingFace housekeeping ─────────────────────────────────────────────────
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
# ─────────────────────────────────────────────────────────────────────────────

import torch
import gc
from transformers import AutoModelForCausalLM, AutoTokenizer


# ── Negative prompt builder ───────────────────────────────────────────────────

_NEG_BASE = (
    "watermark, text, signature, duplicate, "
    "static, no motion, frozen, "
    "poorly drawn, bad anatomy, deformed, disfigured, "
    "extra limbs, missing limbs, floating limbs, disconnected body parts, "
    "micro jitter, flickering, strobing, aliasing, high frequency patterns, "
    "motion artifacts, temporal inconsistency, frame stuttering"
)

# _NEG_INDOOR / _NEG_OUTDOOR removed — LTX-2.3 VAE handles lighting naturally.
# Injecting these fought the model's improved environmental rendering.
_NEG_INDOOR        = ""
_NEG_OUTDOOR       = ""
_NEG_EXPLICIT      = "censored, mosaic, pixelated, black bar, blurred genitals"
_NEG_PORTRAIT_SHOT = "wide angle distortion, fish eye, full body shot"
_NEG_WIDE          = "close-up, portrait crop, tight frame"
# _NEG_NIGHT / _NEG_DAY removed — LTX-2.3 handles exposure natively.
_NEG_NIGHT         = ""
_NEG_DAY           = ""
_NEG_MULTI         = "merged bodies, fused figures, incorrect number of people"
_NEG_PORTRAIT_ORI  = "landscape orientation, letterbox, pillarbox, horizontal crop, widescreen framing"
_NEG_VHS           = "clean digital, sharp edges, 4K, high resolution, pristine quality"
_NEG_HORROR        = "bright happy lighting, warm tones, cheerful atmosphere, soft light"
_NEG_FASHION       = "casual handheld, amateur footage, flat lighting, unposed"
_NEG_SELFIE        = "tripod, gimbal stabilised, smooth camera movement, rack focus, dolly, crane, cinematic bokeh, dramatic depth of field, professional lighting, film grain, colour grade, cinematic lens, landscape orientation"

_NEG_ANIME         = "photorealistic, live action, real person, CGI, 3D render, western cartoon, flat shading"
_NEG_2DCARTOON     = "photorealistic, 3D render, CGI, anime, live action, flat digital art, no line work"
_NEG_3DCGI         = "photorealistic, live action, 2D flat, hand-drawn, sketch, anime, watercolour"
_NEG_STOPMOTION    = "smooth motion, CGI, photorealistic, digital, fluid movement, motion blur"
_NEG_COMICBOOK     = "photorealistic, soft gradients, 3D render, painterly, no line art, anime"
_NEG_CELSHADED     = "photorealistic, soft shading, gradients, painterly, hand-drawn lines, anime"
_NEG_ROTOSCOPE     = "fully animated, cartoon, CGI, no live action base, unnatural movement"
_NEG_CYBERPUNK     = "natural lighting, pastoral, warm tones, daylight, photorealistic skin, muted colour"
_NEG_SCIFI         = "medieval, fantasy, nature, pastoral, historical, period costume, warm earthy tones"

def _build_negative_prompt(result: str, user_input: str, is_portrait: bool = False, style_preset: str = "") -> str:
    combined = (result + " " + user_input + " " + style_preset).lower()
    extras = []

    # FIX: was previously inverted — indoor scene suppresses _NEG_INDOOR (not _NEG_OUTDOOR)
    # _NEG_INDOOR and _NEG_OUTDOOR are intentionally empty for LTX-2.3 (model handles lighting natively).
    # Logic is correct now so re-enabling the strings will work as expected.
    if any(w in combined for w in ["indoor", "room", "interior", "bedroom", "kitchen", "office"]):
        extras.append(_NEG_INDOOR)
    elif any(w in combined for w in ["outdoor", "street", "beach", "forest", "park", "exterior"]):
        extras.append(_NEG_OUTDOOR)

    if any(w in combined for w in ["pussy", "cock", "penis", "vagina", "nude", "naked", "explicit", "nipple", "breast"]):
        extras.append(_NEG_EXPLICIT)

    if any(w in combined for w in ["close-up", "close up", "face shot", "headshot"]):
        extras.append(_NEG_PORTRAIT_SHOT)
    elif any(w in combined for w in ["wide shot", "wide angle", "aerial", "bird's-eye", "establishing"]):
        extras.append(_NEG_WIDE)

    # FIX: _NEG_NIGHT / _NEG_DAY are intentionally empty for LTX-2.3 (improved exposure handling).
    # Conditionals are preserved so re-populating the strings works, but empty strings are not appended.
    if any(w in combined for w in ["night", "dark", "moonlight", "dimly lit", "candlelight"]):
        if _NEG_NIGHT:
            extras.append(_NEG_NIGHT)
    elif any(w in combined for w in ["daylight", "sunny", "golden hour", "bright", "midday"]):
        if _NEG_DAY:
            extras.append(_NEG_DAY)

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


    # Animation styles
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

    # Filter out any empty strings (from removed negatives) and deduplicate
    parts = [p for p in [_NEG_BASE] + extras if p.strip()]
    return ", ".join(parts)


# ── Character attribute pools — mixed independently each run ─────────────────
# Each dimension is picked separately so combinations are near-infinite.
# The LD node injects this as a seed note into the user message, identical
# to the Qwen version. If the user described the character themselves,
# their description takes priority over the seed.

_CHAR_AGES = [
    # Children (kept for non-sexual contexts)
    "8", "9", "10", "11", "12",
    # Teens
    "14", "15", "16", "17", "18",
    # Core range 19–35 — weighted heavily (appears 3x more than 36+)
    "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
    "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
    "30", "31", "32", "33", "34", "35",
    "30", "31", "32", "33", "34", "35",
    # Adults 36–45 — present but rare
    "36", "37", "38", "40", "42", "44",
    # 46+ — only surfaces when context implies it (old/mature/elderly keywords handled in prompt)
    "48", "52", "58",
]

_CHAR_ETHNICITIES = [
    # East Asian
    ("East Asian",      "fair cool-toned skin with a subtle pink undertone"),
    ("East Asian",      "light ivory skin with warm golden undertones"),
    ("Japanese",        "pale skin with cool beige undertones"),
    ("Korean",          "fair skin with a soft peachy-pink flush"),
    ("Chinese",         "light golden-toned skin"),
    # South Asian
    ("South Asian",     "warm medium brown skin with golden undertones"),
    ("South Asian",     "deep brown skin with rich warm undertones"),
    ("Indian",          "light caramel skin with a warm yellow-brown tone"),
    ("Indian",          "deep mahogany skin with warm red undertones"),
    # Southeast Asian
    ("Southeast Asian", "golden tan skin with warm undertones"),
    ("Southeast Asian", "light brown skin with a soft amber glow"),
    ("Filipino",        "medium warm brown skin"),
    ("Vietnamese",      "light olive skin with golden tones"),
    # Middle Eastern / North African
    ("Middle Eastern",  "warm olive skin with subtle golden undertones"),
    ("Middle Eastern",  "light brown skin with honey-gold undertones"),
    ("North African",   "medium warm brown skin with a golden cast"),
    # Black / African descent
    ("Black",           "deep ebony skin with cool blue-black undertones"),
    ("Black",           "rich dark brown skin with warm red undertones"),
    ("Black",           "medium warm brown skin with golden undertones"),
    ("Black",           "deep mahogany skin"),
    ("Black",           "light golden-brown skin"),
    # Latina / Hispanic
    ("Latina",          "warm medium tan skin with golden-brown undertones"),
    ("Latina",          "light olive skin with warm undertones"),
    ("Latina",          "deep warm brown skin"),
    # White / European
    ("White",           "pale freckled skin with pink undertones"),
    ("White",           "fair skin with cool undertones"),
    ("White",           "light skin with warm peachy tones"),
    ("White",           "porcelain skin with visible blue veins at the temples"),
    # Mixed / multiracial
    ("mixed race",      "warm golden-brown skin with cool undertones"),
    ("mixed race",      "light tan skin with a warm olive cast"),
    ("mixed race",      "medium brown skin with golden-red undertones"),
    # Indigenous / Pacific
    ("Indigenous",      "warm copper-brown skin with red undertones"),
    ("Pacific Islander","deep warm tan skin with golden-brown tones"),
]

_CHAR_HAIR_COLOURS = [
    "jet black",
    "dark brown",
    "warm medium brown",
    "auburn",
    "dark auburn",
    "copper red",
    "bright copper",
    "strawberry blonde",
    "honey blonde",
    "ash blonde",
    "platinum blonde",
    "silver-white",
    "silver-streaked dark brown",
    "blue-black",
    "dyed burgundy",
    "dyed deep violet",
    "dyed bleach blonde with dark roots",
    "natural dark brown with caramel highlights",
    "salt-and-pepper grey",
    "warm chestnut brown",
]

_CHAR_HAIR_STYLES = [
    # Natural textures
    "tight 4C coils, natural and full",
    "loose 3B curls, mid-length",
    "thick natural afro, rounded",
    "defined 3C ringlets, shoulder-length",
    "big loose natural curls, voluminous",
    # Protective styles
    "long box braids falling past the shoulders",
    "short box braids, chin-length",
    "thick cornrows flat to the scalp",
    "two-strand twists, loose and mid-length",
    "high bun of twisted locs",
    "long faux locs, loose",
    # Straight styles
    "pin-straight, very long, falling to the waist",
    "pin-straight, blunt cut to the shoulder",
    "sleek straight hair, cut to the chin",
    "straight with a heavy blunt fringe",
    # Wavy styles
    "loose beach waves, mid-back length",
    "tousled waves, shoulder-length",
    "soft waves with a side part, collarbone length",
    # Short styles
    "cropped pixie cut, textured",
    "buzzed close on the sides, longer on top",
    "short tapered cut with volume at the crown",
    "chin-length bob, blunt",
    "asymmetric bob, longer on one side",
    # Updos / tied
    "high ponytail, sleek",
    "messy bun with loose strands framing the face",
    "half-up half-down, loosely pinned",
    "low bun, tight and smooth",
    # Long styles
    "very long straight hair, centre-parted",
    "long layered hair with curtain bangs",
    "long thick hair in a loose braid over one shoulder",
]

_CHAR_BODY_TYPES = [
    # Slender / lean
    "slender build with narrow shoulders",
    "lean and tall with long limbs",
    "slim with a flat stomach and narrow hips",
    "petite and slender, small-framed",
    "thin with delicate bone structure",
    # Athletic
    "athletic build with defined shoulders",
    "muscular and toned with broad shoulders",
    "lean and athletic with visible muscle definition",
    "strong legs and a narrow waist",
    "compact and powerfully built",
    # Average / medium
    "average build with soft curves",
    "medium build with a naturally rounded figure",
    "medium height, balanced proportions",
    "slightly soft figure with gentle curves",
    # Curvy / full-figured
    "full hourglass figure with wide hips and a defined waist",
    "curvy with a round bust and full hips",
    "voluptuous with a soft stomach and generous curves",
    "big-busted with a narrow waist and wide hips",
    "full-figured and tall with a commanding presence",
    # Petite / short
    "petite with a small frame and short stature",
    "short and curvy with a compact figure",
    "tiny frame, barely five feet tall",
    # Plus size / soft
    "plus-size with a soft round belly and full arms",
    "full-figured with heavy thighs and a wide waist",
    "chubby with round cheeks and a soft generous body",
    "fat with a pronounced belly and thick legs",
    "large and soft, with wide hips and heavy breasts",
    # Tall
    "tall and willowy with long legs",
    "statuesque, over six feet, lean",
]


def _build_char_seed(rng: random.Random) -> str:
    """Assemble a character description by picking each dimension independently."""
    age             = rng.choice(_CHAR_AGES)
    ethnicity, skin = rng.choice(_CHAR_ETHNICITIES)
    hair_colour     = rng.choice(_CHAR_HAIR_COLOURS)
    hair_style      = rng.choice(_CHAR_HAIR_STYLES)
    body_type       = rng.choice(_CHAR_BODY_TYPES)
    return (
        f"a {age}-year-old {ethnicity} woman, "
        f"{hair_colour} hair in a {hair_style}, "
        f"{skin}, "
        f"{body_type}"
    )


class LTX2PromptArchitect:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "bypass": ("BOOLEAN", {"default": False, "tooltip": "When ON, skips the LLM entirely and sends your text straight to the prompt encoder. Use for manual prompts or testing."}),
                "user_input": ("STRING", {
                    "multiline": True,
                    "default": "a woman walks through a rain-soaked city street at night",
                    "tooltip": "Describe what you want to happen. Can be a rough idea, a sentence, or numbered steps (1. she stands 2. she walks). The LLM expands this into a full cinematic prompt."
                }),
                "creativity": ([
                    "0.5 - Strict & Literal",
                    "0.8 - Balanced Professional",
                    "1.0 - Artistic Expansion"
                ], {"default": "0.8 - Balanced Professional", "tooltip": "Controls how closely the LLM sticks to your input. 0.5 is very literal and precise — closest to your exact words. 0.8 is balanced with professional cinematic language. 1.0 adds more creative flair and expansion beyond your input."}),
                "seed": ("INT", {
                    "default": -1,
                    "min": -1,
                    "max": 2**31 - 1,
                    "step": 1,
                    "display": "number",
                    "tooltip": "Set a fixed seed to get the same prompt expansion every run. Use -1 for a random result each time."
                }),
                "invent_dialogue": ("BOOLEAN", {"default": True, "tooltip": "When ON, the LLM invents natural spoken dialogue for characters woven into the scene. When OFF, only uses dialogue you wrote yourself (in quotes), or generates no dialogue at all."}),
                "keep_model_loaded": ("BOOLEAN", {"default": False, "tooltip": "Keep the LLM in VRAM between runs for faster generation. Turn OFF to free VRAM immediately after each run — recommended if you have less than 16GB VRAM."}),
                "offline_mode": ("BOOLEAN", {"default": False, "tooltip": "Turn ON if you have no internet. Uses locally cached models only. Turn OFF to allow auto-download from HuggingFace on first run."}),
                "frame_count": ("INT", {
                    "default": 192,
                    "min": 24,
                    "max": 960,
                    "step": 1,
                    "display": "number",
                    "tooltip": "Match this to your video LENGTH setting. Controls pacing — the LLM uses this to calculate how many actions fit in the clip. 24fps = 1 second, so 192 = 8 seconds."
                }),
                "style_preset": (list(LTX2PromptArchitect.STYLE_PRESETS.keys()), {
                    "default": "None — let the LLM decide",
                    "tooltip": "Sets the visual aesthetic for the prompt — lighting, colour, camera, mood. Also drives the FPS output pin automatically: cinematic presets = 24, realistic/action = 30. Wire FPS to your video and audio save nodes."
                }),
                "portrait_mode": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Force 9:16 vertical framing for TikTok, Reels, and Shorts. LTX-2.3 has native portrait support — use this to take advantage of it. Overrides style preset orientation."
                }),
                # ── Model selector ──────────────────────────────────────────
                "model": ([
                    "8B - NeuralDaredevil (High Quality)",
                    "3B - Llama-3.2 Abliterated (Low VRAM)",
                ], {"default": "8B - NeuralDaredevil (High Quality)", "tooltip": "Choose your LLM. 8B gives better quality prompts and handles explicit content well. 3B is faster and uses less VRAM. Both download automatically on first run."}),
                # ── Local paths for offline mode ────────────────────────────
                "local_path_8b": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "e.g. C:\\Users\\YOU\\.cache\\huggingface\\hub\\models--mlabonne--NeuralDaredevil-8B-abliterated\\snapshots\\YOUR_HASH",
                    "tooltip": "Optional. Paste the full path to your locally downloaded NeuralDaredevil 8B snapshot folder. Leave blank to use the HuggingFace cache automatically."
                }),
                "local_path_3b": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Local path to Llama-3.2 3B snapshot folder",
                    "tooltip": "Optional. Paste the full path to your locally downloaded Llama 3.2 3B snapshot folder. Leave blank to use the HuggingFace cache automatically."
                }),
            },
            "optional": {
                "use_scene_context": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Enable or disable scene_context without disconnecting the wire. Turn OFF to use your text input only and ignore the wired vision description."
                }),
                "scene_context": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "Optional: vision description from LTX-2 Vision Describe node",
                    "tooltip": "Wire the output from the LTX-2 Vision Describe node here. The LLM will use your image as the authoritative starting point and animate it forward from your prompt."
                }),
                "lora_triggers": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Optional: LoRA trigger words e.g. 'ohwx woman, film grain'",
                    "tooltip": "Paste your LoRA trigger words here. They will be injected at the very start of every generated prompt automatically — never buried or forgotten."
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "INT", "STRING")
    RETURN_NAMES = ("PROMPT", "PREVIEW", "NEG_PROMPT", "FPS", "HISTORY")
    FUNCTION = "generate"
    CATEGORY = "LTX2"

    # ── Style presets ─────────────────────────────────────────────────────────
    # Maps dropdown label → (style instruction, portrait flag)
    STYLE_PRESETS = {
        "None — let the LLM decide": ("", False),
        # Cinematic tiers
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
            "Wide lenses — 24mm to 35mm. Vast compositions that make people feel small against the world. "
            "Camera: sweeping crane moves, slow orbital shots, long tracking shots across terrain. "
            "Colour grade: rich, contrasty — deep shadows, luminous highlights. "
            "Kodak 5219 for natural daylight scenes, ARRI Alexa for clean digital grandeur. "
            "Sound: environmental and large — wind, distance, the weight of open space. "
            "Every frame should feel like a poster. Build depth with foreground elements. "
            "Motion blur on fast movement. Natural motion blur, 180 degree shutter equivalent.", False),
        "Cinematic — Intimate close-up": (
            "STYLE: Intimate close-up cinema. The entire world is a face, a hand, a detail. "
            "Focal lengths: 85mm to 135mm f/1.2 to f/1.8. Razor-thin depth of field — "
            "one eye sharp, the other already soft. Bokeh is smooth and organic. "
            "Camera: barely moves — micro drifts and imperceptible breathing. "
            "Colour grade: skin-tone faithful, no heavy colour casts. Warm and close. "
            "Lighting: one soft source, one fill, nothing else. "
            "Sound: amplified intimacy — breath, the swallow of saliva, fabric against skin, heartbeat proximity. "
            "Reveal character through detail — a tightening jaw, a flicker of the eye, fingers finding each other. "
            "This is portraiture as cinema.", False),
        # Cinematic / Narrative
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
            "Soft shadows, glowing skin tones. Wide lenses. Emotional, sweeping camera movement. "
            "Colour grade: warm, slightly overexposed highlights.", False),
        "Horror — desaturated, harsh contrast": (
            "STYLE: Horror. Heavily desaturated colour, crushed blacks. Harsh top-down or under-lighting. "
            "Camera movements are slow and uneasy — never reassuring. "
            "Framing leaves negative space — empty doorways, dark corners. No warmth in the image.", False),
        # Erotic / Adult
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
        "Amateur — naturalistic, raw": (
            "STYLE: Amateur home video aesthetic. Slightly overexposed. Natural indoor lighting — lamps, overhead. "
            "Camera is handheld and slightly uncertain. No cinematic framing. "
            "Colour: ungraded, as-shot. The imperfection is intentional.", False),
        # Action / Energy
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
            "Sync camera and body movement to the implied beat.", False),
        # Aesthetic / Visual
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
            "Lens: wide aperture with heavy bokeh. Light sources bloom and halo.", False),
        "Gritty realism — flat, natural light": (
            "STYLE: Gritty realism. Flat colour grade, no cinematic enhancement. Natural light only — "
            "whatever is available in the location. Camera is direct and unsentimental. "
            "No stylisation. The scene is shot as if it is actually happening.", False),
        # Speciality
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
        # Animation
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

    # ── FPS map — auto output based on style preset ───────────────────────────
    # Single INT output — wire to video save node and audio save node
    # 24 = cinematic  |  30 = realistic / action
    PRESET_FPS = {
        # Cinematic tiers
        "Cinematic — Drama":                        24,
        "Cinematic — Epic":                         24,
        "Cinematic — Intimate close-up":            24,
        # Cinematic / Narrative
        "None — let the LLM decide":                24,
        "Slow-burn thriller":                       24,
        "Handheld documentary":                     30,  # TV/doc feel
        "High fashion editorial":                   24,
        "Noir — deep shadows, venetian light":      24,
        "Golden hour drama":                        24,
        "Horror — desaturated, harsh contrast":     24,
        # Adult / Sensual
        "Erotic cinema — tasteful, cinematic":      24,
        "Explicit — direct, anatomical":            30,
        "Voyeur — handheld, observational":         30,
        "Softcore editorial — lingerie-adjacent":   24,
        "Amateur — naturalistic, raw":              30,
        # Action / Energy
        "Action blockbuster":                       30,
        "Sports documentary":                       30,
        "Music video — stylised":                   30,
        # Aesthetic / Visual
        "Lo-fi home video — VHS":                   24,
        "Hyper-real 4K — clinical sharpness":       30,
        "Dreamy — soft focus, slow motion":         24,
        "Gritty realism — flat, natural light":     30,
        # Speciality
        "POV — first person, immersive":            30,
        "Portrait vertical — 9:16 mobile":          30,
        "Selfie — self-shot, arm's length":        30,  # self-shot vertical, 30fps

        # Animation
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

    # ── Model registry ────────────────────────────────────────────────────────
    MODELS = {
        "8B - NeuralDaredevil (High Quality)": "mlabonne/NeuralDaredevil-8B-abliterated",
        "3B - Llama-3.2 Abliterated (Low VRAM)": "huihui-ai/Llama-3.2-3B-Instruct-abliterated",
    }

    # ── Style label map — class-level constant (FIX: was rebuilt inside generate() every call) ──
    # These labels are prepended to the output so LTX-2.3's text encoder sees the render style.
    # Kept in sync with STYLE_PRESETS and PRESET_FPS here at class scope.
    PRESET_STYLE_LABEL = {
        # Cinematic tiers
        "Cinematic — Drama":                        "Cinematic drama, shallow depth of field, Kodak 2383.",
        "Cinematic — Epic":                         "Cinematic epic, vast wide-angle compositions.",
        "Cinematic — Intimate close-up":            "Intimate close-up cinema, 85mm-135mm, razor-thin depth of field.",
        # Cinematic
        "Slow-burn thriller":                       "Slow-burn psychological thriller.",
        "Handheld documentary":                     "Handheld documentary footage.",
        "High fashion editorial":                   "High fashion editorial video.",
        "Noir — deep shadows, venetian light":      "Classic noir, black and white, venetian blind shadows.",
        "Golden hour drama":                        "Golden hour cinematic drama.",
        "Horror — desaturated, harsh contrast":     "Horror film, desaturated, harsh contrast.",
        # Adult
        "Erotic cinema — tasteful, cinematic":      "Tasteful erotic cinema, warm intimate lighting.",
        "Explicit — direct, anatomical":            "Explicit adult video, direct lighting.",
        "Voyeur — handheld, observational":         "Voyeuristic handheld footage.",
        "Softcore editorial — lingerie-adjacent":   "Softcore editorial, fashion magazine aesthetic.",
        "Amateur — naturalistic, raw":              "Amateur home video, naturalistic.",
        # Action
        "Action blockbuster":                       "Action blockbuster, teal and orange grade.",
        "Sports documentary":                       "Sports documentary footage.",
        "Music video — stylised":                   "Stylised music video.",
        # Aesthetic
        "Lo-fi home video — VHS":                   "Lo-fi VHS home video footage.",
        "Hyper-real 4K — clinical sharpness":       "Hyper-real 4K, clinical sharpness.",
        "Dreamy — soft focus, slow motion":         "Dreamy soft focus, slow motion.",
        "Gritty realism — flat, natural light":     "Gritty realism, flat natural light.",
        # Speciality
        "POV — first person, immersive":            "First-person POV footage.",
        "Portrait vertical — 9:16 mobile":          "Vertical 9:16 mobile video.",
        "Selfie — self-shot, arm's length":        "Selfie video, self-shot at arm's length, vertical 9:16.",
        # Animation
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

    # ── System prompt ─────────────────────────────────────────────────────────
    SYSTEM_PROMPT = """You are a cinematic prompt writer for LTX-2.3, an AI video generation model. Expand the user's rough idea into a precise, director-level, video-ready prompt. Be specific — LTX-2.3 rewards complexity and detail.

LTX-2.3 CAPABILITIES — exploit all of these:
- Complex prompts work. Multiple subjects, spatial relationships, layered actions, stylistic constraints — specificity wins, do not dumb it down.
- Rebuilt VAE renders fine detail: fabric weave, individual hair strands, skin texture, surface wear, material finish. Describe these.
- Stronger prompt adherence — you can direct camera AND subject motion simultaneously.
- Native portrait up to 1080x1920 — compose vertically, not as cropped landscape.
- Improved audio vocoder — describe sound with tone, intensity, environment. Sound is always present. Exception: if the scene has no people and no music, use environmental/physical sound only — no voices, no crowd noise, no implied human presence.
- Reduced motion freezing — always include motion. Static prompts produce static video.

SCENE INTEGRITY:
Build outward from what the user gave you — do not contradict or override it.
If the user described a location, enrich it with specific textures and atmosphere that fit: a city street becomes "wet asphalt reflecting neon, steam rising from a grate, the cold blue cast of a streetlamp". A café becomes "warm tungsten light, fogged glass, the grain of the wooden tabletop".
If the user gave NO location, shoot in a neutral unspecified space — do not invent a warehouse, forest, or bedroom they didn't ask for.
Do NOT add: rose petals, candles, silk sheets, glitter, sparkles, or sentimental filler that isn't grounded in the scene.
Do NOT invent props or characters the user didn't mention.
Every addition must be (a) from the user's input, (b) a texture/material/atmosphere detail that enriches what they described, or (c) a necessary camera/staging decision.

CAMERA ORIENTATION — IMPORTANT:
The DEFAULT assumption is that the subject FACES the camera unless the user's input clearly requires otherwise.
ONLY write "Rear view" or "camera follows from behind" if the user explicitly stated one of these: "from behind", "rear view", "back view", "follow her from behind", "watches her from behind", "camera behind", "over her shoulder from behind".
Do NOT default to rear view just because the subject is walking or moving. A woman walking toward camera or facing camera is the correct default. Rear view is an exception, not the rule.

SCENE DIRECTION — build the prompt in this order:
1. Style & genre — use the STYLE INSTRUCTION as the aesthetic anchor. Where it fits the mood, weave a film stock or camera system reference into the prose naturally — e.g. 'the image carries a Kodak 2383 warmth', 'shot on an ARRI Alexa, clean and clinical', 'Fuji Eterna desaturation flattens the shadows'. NEVER output film stock as a bracketed tag or prefix like [Kodak 5219]. It must read as part of a sentence, not a label.
2. Shot type & camera angle — specific cinematographic terms: medium close-up, OTS, Dutch angle, bird's-eye, tracking shot. Never vague.
3. Lens & optics — ALWAYS include focal length AND aperture in every prompt: "85mm f/1.4", "35mm f/2.8", "50mm anamorphic equivalent f/2.0", "24mm wide f/4". This is non-negotiable — it controls depth, edge sharpness, and spatial compression. Also include: natural motion blur, 180 degree shutter equivalent — mandatory in every prompt. CRITICAL: Lens, motion blur, and shutter must be woven into the prose as part of a sentence — NEVER output them as a labelled appendix like "Lens: 50mm f/2.0." or "Camera angle: medium close-up." at the end. Wrong: "...she looks away. Lens: 50mm f/2.0, natural motion blur." Right: "...the camera, a 50mm f/2.0, slowly pushes in, natural motion blur and 180-degree shutter equivalent rendering her movement fluid."
4. Character — ALWAYS state age as a specific number e.g. "a 27-year-old woman". Default age range is 18–35 unless the user's input implies otherwise. Only use ages 40+ if the user mentions words like "older", "mature", "middle-aged", "elderly", "old man", "old woman". Only use child/teen ages (under 18) if the user's input explicitly places the character in a school, childhood, or teen context — and NEVER assign child/teen ages to any sexual or suggestive content. Then: hair texture and colour, skin tone, body type, clothing described with fabric and material ("a fitted black cotton crop top", "worn light-wash denim jeans", "a loose cream silk blouse"). Use the exact words the user used for body parts. Include subtle emotional cues and micro expressions: "the corners of her lips tighten slightly", "her eyes momentarily lose focus", "a faint crease forms between her brows". These create depth and life in the character.
5. Scene & environment — location, time of day, lighting quality and direction, colour temperature, surface textures ("scuffed hardwood floor", "rain-streaked glass", "warm tungsten interior"). Only what the user described. Avoid high frequency visual patterns in clothing, backgrounds, and surfaces — these cause flickering artifacts. Favour solid colours, simple textures, and smooth surfaces.
6. Spatial blocking — MANDATORY and explicit. Define: left/right position, foreground/background depth, approximate distance between subjects, who faces what. "She stands centre-left in the foreground, facing camera. He sits two metres behind her at the right edge of frame, slightly soft." For single subjects: anchor them in frame — "She stands centre-frame, mid-shot, facing camera, the background three metres behind her." Block every scene like a director.

ACTION & MOTION:
7. Motion — VERBS OF PROGRESSION are primary. State all four simultaneously when possible: who moves, what moves, how they move, what the camera does. "She steps forward and turns as the camera tracks left and slowly pushes in." Layer actions — LTX-2.3 holds complex motion structure. If the user's input is genuinely static (a portrait, a held moment), add ONE subtle environmental motion only: a camera drift, wind in hair, a background figure. Do not pile on micro-movements — use directed camera or subject action first. For smooth motion: use stable dolly movement, smooth gimbal tracking, constant speed pan, controlled camera path. Avoid chaotic movement, irregular motion paths, or rapid zooming unless stylistically required.
8. Texture in motion — how materials behave as things move: "the fabric pulls taut across her hips", "her hair lifts and separates", "the denim creases at the knee as she bends". LTX-2.3 renders this.
9. Camera movement — prose verbs only, never bracketed. "The shot slowly pushes in" not "(Push in)". Vocabulary: dolly in/out, rack focus, whip pan, push in, crane up, handheld drift, slow orbit, creep forward, track right, stabilised gimbal arc.

SOUND — always present, always described:
10. Sound is MANDATORY in every prompt — there are no silent scenes. Weave it as descriptive prose with tone, intensity, and environment. Max 2 sounds active per beat. When action and sound are synchronised, describe the timing explicitly: "the sticks strike on every downbeat", "the click of the shutter precisely as her fingers press", "footsteps landing on each beat of the track". Temporal sync language strengthens audio-visual coherence.
- Standard scenes: physical, real-world sounds with full sensory detail. Not just "footsteps" — "the sharp, rhythmic clack of heels on cold marble, each step ringing with a hollow metallic echo." Not just "rain" — "rain striking the glass in irregular bursts, a low persistent hiss beneath it." Describe what the sound feels like in the body, not just what it is.
- Music/dance/club/performance scenes: describe the track as physical sensation — "a deep kick drum at 128bpm punches through the floor, the sub-bass felt in the chest", "sharp hi-hats tick over a slow rolling groove", "the mix drops into a heavy bass swell that fills the room". Do NOT silence music. Do NOT reduce it to "music plays".
- Never use [AMBIENT: ...] tags. No abstract emotional audio — no "tension fills the air", no "heartbeat of the city".

CRITICAL RULES:
- NEVER write scene endings or closing paragraphs. Prompts describe ongoing action, not conclusions. Never use: "the scene ends", "the shot ends", "comes to a close", "fades to black", "the camera cuts", "hard stop", "scene closes", "camera lingers on the final". Also forbidden: winding-down final sentences that summarise the mood and close the scene — e.g. "In this peaceful moment, the world fades, leaving only...", "...and the quiet satisfaction of a perfect morning ritual.", "...the only sound the gentle hum of...", "...nothing remains but...". These are scene closings dressed as prose. Cut before them. The scene is always mid-action, never concluding.
- NEVER invent additional characters. If the user describes one person, there is one person. If the user describes two people, there are two. Do NOT add bystanders, passers-by, partners, or observers unless the user explicitly wrote them into the scene.

DIALOGUE — follow the DIALOGUE INSTRUCTION exactly. Inline prose with attribution. No [DIALOGUE: ...] tags.

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
- Always include natural motion blur and 180 degree shutter equivalent — every prompt, no exceptions.
- Always include lens focal length and aperture — every prompt, no exceptions.
- Avoid high frequency patterns in clothing, backgrounds, and surfaces — these cause flickering.
- Flowing prose, not lists

OUTPUT RULES:
Output ONLY the prompt. No preamble, no "Sure!", no "Here's your prompt:", no compliance notes, no word counts, no brackets after the final sentence. Begin immediately with the shot or style description. End with the last sentence of the scene."""

    _PREAMBLE_RE = re.compile(
        r"^(Sure!?|Certainly!?|Absolutely!?|Of course!?|Here(?:'s| is).*?:|Great!?|"
        r"LTX-?2(?:\.\d)?(?:\s+\w+)*\s*prompt\s*:|Prompt\s*:|Output\s*:|Scene\s*:)[^\n]*\n?",
        re.IGNORECASE,
    )
    _ROLE_BLEED_RE = re.compile(
        r"\s*(assistant|user|system|<\|[^|>]*\|>)\s*$",
        re.IGNORECASE,
    )

    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.loaded_model_key = None
        self._last_portrait = False
        self._last_style = ""
        self._stop_token_ids = []  # FIX: cached at load time, not rebuilt every generate() call

    def load_model(self, model_key: str, offline_mode: bool, local_path: str):
        if self.model is not None and self.loaded_model_key != model_key:
            print(f"[LTX2] Model switch detected: {self.loaded_model_key} → {model_key}")
            self.unload_model()

        if self.model is not None:
            return

        if offline_mode:
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["HF_DATASETS_OFFLINE"] = "1"
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
            os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
            print("[LTX2] Offline mode ON — no network calls will be made.")
        else:
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
            os.environ.pop("HF_DATASETS_OFFLINE", None)
            os.environ.pop("HF_HUB_OFFLINE", None)
            print("[LTX2] Offline mode OFF — will download if needed.")

        hf_model_id = self.MODELS[model_key]

        if local_path.strip():
            model_source = local_path.strip()
            print(f"[LTX2] Using local path: {model_source}")
        elif offline_mode:
            model_source = hf_model_id
            print(f"[LTX2] Using HF cache for: {hf_model_id}")
        else:
            print(f"[LTX2] Auto-downloading if needed: {hf_model_id}")
            # Ensure huggingface_hub is available — install it if missing.
            # ComfyUI environments don't always include it even though transformers does.
            try:
                import huggingface_hub as _hfhub
            except ImportError:
                print("[LTX2] huggingface_hub not found — installing now...")
                import subprocess, sys
                subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub", "-q"])
                import huggingface_hub as _hfhub
                print("[LTX2] huggingface_hub installed successfully.")

            try:
                from huggingface_hub import snapshot_download
                print(f"[LTX2] Resolving model from HuggingFace: {hf_model_id}")
                model_source = snapshot_download(
                    hf_model_id,
                    ignore_patterns=["*.gguf"],
                )
                print(f"[LTX2] Model ready at: {model_source}")
            except Exception as e:
                print(f"[LTX2] snapshot_download failed: {e}")
                print(f"[LTX2] Falling back to from_pretrained direct download for: {hf_model_id}")
                model_source = hf_model_id

        print(f"[LTX2] Loading: {model_key}")

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_source,
            local_files_only=offline_mode,
        )

        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

        self.model = AutoModelForCausalLM.from_pretrained(
            model_source,
            device_map="auto",
            torch_dtype=dtype,
            trust_remote_code=True,
            local_files_only=offline_mode,
        )

        self.model.config.use_cache = True
        self.model.eval()
        self.loaded_model_key = model_key
        # FIX: cache stop token IDs at load time — no need to recompute every generate() call
        self._stop_token_ids = self._build_stop_token_ids()
        print(f"[LTX2] Loaded: {model_key}")

    def unload_model(self):
        """
        Hard VRAM free — equivalent to ComfyUI right-click Free Memory.
        Does NOT just move to CPU (that leaves the reserved block sitting).
        Destroys tensors in place, resets the CUDA allocator, and tells
        ComfyUI's model manager to also drop whatever it is holding.
        """
        if self.model is not None:
            # Destroy every tensor in place so CUDA allocator releases pages
            try:
                for _name, module in list(self.model.named_modules()):
                    for _pname, param in list(module.named_parameters(recurse=False)):
                        try:
                            param.data = torch.empty(0)
                        except Exception:
                            pass
                    for _bname, buf in list(module.named_buffers(recurse=False)):
                        try:
                            module._buffers[_bname] = None
                        except Exception:
                            pass
            except Exception as e:
                print(f"[LTX2] Tensor destroy warning: {e}")

        # Delete Python references
        try:
            del self.model
        except Exception:
            pass
        try:
            del self.tokenizer
        except Exception:
            pass

        self.model = None
        self.tokenizer = None
        self.loaded_model_key = None

        # Triple gc — catches circular refs from transformers internals
        gc.collect()
        gc.collect()
        gc.collect()

        if torch.cuda.is_available():
            try:
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
                # Reset the caching allocator entirely — this is what actually
                # releases the "reserved but not allocated" block ComfyUI shows
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.empty_cache()
            except Exception as e:
                print(f"[LTX2] CUDA flush warning: {e}")

        # Tell ComfyUI model manager to drop everything it is holding too
        # (same calls ComfyUI makes on Free Memory / Unload Models)
        try:
            import comfy.model_management as mm
            mm.unload_all_models()
            mm.soft_empty_cache()
            print("[LTX2] ComfyUI mm.unload_all_models + soft_empty_cache done.")
        except Exception as e:
            print(f"[LTX2] ComfyUI mm call skipped: {e}")

        if torch.cuda.is_available():
            try:
                allocated = torch.cuda.memory_allocated() / 1024**3
                reserved  = torch.cuda.memory_reserved()  / 1024**3
                print(f"[LTX2] VRAM after free: {allocated:.2f}GB allocated / {reserved:.2f}GB reserved")
            except Exception:
                pass
        else:
            print("[LTX2] Model unloaded (no CUDA).")

    @staticmethod
    def _clean_output(text: str) -> str:
        text = text.strip()

        # Strip Qwen3 thinking blocks
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # 1. Strip leading preamble
        text = LTX2PromptArchitect._PREAMBLE_RE.sub("", text)

        # 2. Strip trailing role bleed
        text = LTX2PromptArchitect._ROLE_BLEED_RE.sub("", text)

        # 3. Strip inline role injections between sentences
        text = re.sub(
            r"\.(assistant|user|system|<\|[^|>]*\|>)\s*\n",
            ".\n",
            text,
            flags=re.IGNORECASE,
        )

        # 4. Strip trailing Note: blocks
        text = re.sub(r"\s*\n+Note:.*$", "", text, flags=re.DOTALL).strip()

        # Strip AMBIENT tag leftovers
        ambient_match = re.search(r"\[AMBIENT:[^\]]*\]", text, flags=re.IGNORECASE)
        if ambient_match:
            text = text[:ambient_match.end()].strip()

        text = re.sub(r"\s*\(Lora:[^)]*\)\s*$", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*\(Note:.*$", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r"[\s)]{3,}$", "", text).strip()

        text = re.sub(
            r"\s*\n+\d+\s+tokens[\s,].*$", "", text, flags=re.DOTALL | re.IGNORECASE
        ).strip()
        text = re.sub(
            r"\s*\n+(Please let me know|Let me revise|No further revision|Confirmed\.|"
            r"Written to meet|The scene is now over|The output ends|The task is|The task was|"
            r"The goal was|Nothing more|No continuation|No additional|The response does not|"
            r"It does not continue|It ceases when|Any such statement|"
            r"Output length:|Action count:|Total time:|Last character:|I avoided|I wrote|"
            r"I adhered|I hope this|Thank you for your|Please confirm|I submitted|"
            r"I can revise|feel free to instruct).*$",
            "", text, flags=re.DOTALL | re.IGNORECASE,
        ).strip()

        text = re.sub(
            r"\s*(Ended\.\s*\d+\s*actions|"
            r"\d+\s+actions[\.,]\s*\d+\s+tokens|"
            r"\d+\s+tokens[\.,]\s*Done|"
            r"Done\.\s+\d+\s+seconds|"
            r"Finished\.\s+\d+|"
            r"The end\.\s+\d+\s+seconds|"
            r"Fading to black\.\s+The end|"
            r"The model stops|The output ends here|The scene ends here|"
            r"It\'s complete now|All done\.|Stop now\.|"
            r"End of prompt|End of output|No more to add|Nothing to revise|"
            r"The work is (?:done|finished|complete)|The prompt is (?:done|finished|complete)|"
            r"No further writing|No more writing|Stop\.\s+Finish|Finished\.\s+Complete|"
            r"The scene is complete|The scene is over|Complete\.\s+Finished|"
            r"Hard stop\.\s+End\.|Hard stop\.\s+The end\.|"
            r"Hard stop\.\s+End of scene\.|"
            r"The camera does not move again\.|"
            r"The man is gone\.|The woman is gone\.|"
            r"The market continues without (?:him|her|them)\.|"
            r"No more\.\s+Silence\.|End\.\s+No more\.|"
            r"a (?:stark|final) reminder of the .{5,60} style|"
            r"a testament to the .{5,60} attention to detail|"
            r"Done\.\s+No more|BorderSide:|"
            r"\(End of scene\)|\(End of Scene\)|End of scene\.|End of Scene\.)",
            "", text, flags=re.DOTALL | re.IGNORECASE,
        ).strip()

        text = re.sub(r"(\s*\b(\w)\b\s*){10,}", " ", text).strip()
        text = re.sub(r"\s*\(\d+\s+tokens?[^)]*\)", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*(\([^)]{5,120}\)\s*){2,}$", "", text, flags=re.DOTALL).strip()
        text = re.sub(
            r"\s*\([^)]{0,200}(no setup|no resolution|action count|actions adhered|"
            r"token count|pacing|dialogue integrated|character age|inline prose|"
            r"no padding|no extraneous|exactly \d+ action|hard stop|BorderSide)[^)]{0,200}\)\s*$",
            "", text, flags=re.IGNORECASE | re.DOTALL,
        ).strip()

        text = re.sub(r"\(Exact timing:.*?\)", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r"\s*\n*(token|word)\s+count\s*:\s*\d+.*$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        text = re.sub(r"\[TIME LIMIT[^\]]*\]", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\[PACING[^\]]*\]", "", text, flags=re.IGNORECASE).strip()

        # Catch pacing instruction bleed — model echoing "Hard stop." or token counts mid-prose
        text = re.sub(r'\.\s+Hard stop\..*$', '.', text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r'\s+Hard stop\..*$', '', text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r'\.\s+\d+\s+tokens?\b.*$', '.', text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r'\.\s+\d+\s+words?\b.*$', '.', text, flags=re.DOTALL | re.IGNORECASE).strip()
        # Catch "The total duration of the scene is X seconds..." summary bleed
        text = re.sub(r'\.?\s+The total duration of the scene.*$', '.', text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r'\.?\s+The (scene\'?s? )?total (duration|running time).*$', '.', text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r',?\s+with\s+(three|two|four|five|\d+)\s+distinct\s+actions.*$', '.', text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r"\s*\(\d+\s+seconds?\)\s*$", "", text).strip()
        text = re.sub(r"\s*\(\d+:\d+\s*[-–]\s*\d+:\d+\)\s*", " ", text).strip()
        text = re.sub(r"\(The action takes up roughly[^\)]*\)", " ", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\((?:DOWN|UP|PULL|PUSH|ZOOM|HOLD|FADE|PAN|TILT|TRUCK|DOLLY|AMBIENT)[^\)]{0,80}\)", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\[AMBIENT:\s*([^\]]*)\]", r"\1", text, flags=re.IGNORECASE).strip()
        # Strip bracketed film stock / camera tags the LLM sometimes outputs as labels
        text = re.sub(r"\[(Kodak|ARRI|Fuji|Film stock|film stock)[^\]]{0,80}\]\s*", "", text, flags=re.IGNORECASE).strip()
        # Strip labelled technical appendix lines the LLM sometimes adds at the end
        # e.g. "Lens: 50mm f/2.0, natural motion blur." or "Camera angle: medium close-up."
        text = re.sub(
            r"\b(Lens|Camera angle|Focal length|Shutter|Motion blur|Aperture)\s*:\s*[^.\n]{5,120}[.\n]?\s*$",
            "", text, flags=re.IGNORECASE
        ).strip()
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        # Strip inline parenthetical annotation leaks e.g. (camera angle: bird's-eye), (genre: nature, style: drone)
        text = re.sub(r"\([a-z][a-z ,]+:[^)]{3,100}\)", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s{2,}", " ", text).strip()

        # Strip instruction label echoes
        text = re.sub(
            r"^(Action Beat \d+:|Undressing Segment:|Flash/Reveal Segment:|Note:|Scene Instruction:|Pacing:|Dialogue Instruction:).*",
            "", text, flags=re.IGNORECASE | re.MULTILINE,
        ).strip()

        # Strip trailing lone bracket
        text = re.sub(r'\s*[\(\[]\s*$', '', text).strip()

        # Strip trailing poetic wind-down / closing paragraph
        # Catches: "In this peaceful moment, the world fades, leaving only..."
        # and "...the quiet satisfaction of a perfect morning ritual." style closings
        text = re.sub(
            r',?\s*(In this (peaceful|serene|quiet|tender|intimate|still|languid|tranquil|soft) (moment|scene|instant)[^.]{0,200}\.)\s*$',
            "", text, flags=re.IGNORECASE | re.DOTALL
        ).strip()
        text = re.sub(
            r'[,.]?\s*(leaving only (the [a-z ]{3,60}(of|and)[^.]{3,80})\.?)\s*$',
            ".", text, flags=re.IGNORECASE
        ).strip()
        text = re.sub(
            r'[,.]?\s*(the (quiet|soft|gentle|only) (satisfaction|warmth|rhythm|rustle|hum|sound|glow) of [^.]{5,80}\.)\s*$',
            ".", text, flags=re.IGNORECASE
        ).strip()
        text = re.sub(
            r'[,.]?\s*((nothing|no[- ]one) remains? (but|except) [^.]{5,80}\.)\s*$',
            ".", text, flags=re.IGNORECASE
        ).strip()

        # Catch additional wind-down closing variants
        text = re.sub(
            r'[,.]?\s*[Tt]he (only (sound|accompaniment|thing|noise)|sound of [a-z ]{3,40}) (is|was|remains?) the only [^.]{5,80}\.\s*$',
            ".", text, flags=re.IGNORECASE
        ).strip()
        text = re.sub(
            r'[,.]?\s*[Tt]he (only (accompaniment|sound|thing)) to (her|his|their) (quiet|soft|gentle) [a-z]{3,30}\.\s*$',
            ".", text, flags=re.IGNORECASE
        ).strip()

        # Catch "The scene ends there" leaking mid-prose after a sentence
        text = re.sub(r'\.\s+The scene ends there[^.]*\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+before the scene fades to black[^.]*\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'\.?\s+[Tt]he scene fades to black[^.]*\.', '.', text, flags=re.IGNORECASE).strip()
        text = re.sub(r',?\s+as the scene fades[^.]*\.', '.', text, flags=re.IGNORECASE).strip()

        # ── Repetition loop detection ─────────────────────────────────────────
        # Catches runaway "No more. No more. No more." style loops
        # Safe approach: detect a short phrase repeated 5+ times at end of text
        rep_match = re.search(
            r'((?:\b\w[\w\'\-]*\b[\s\.,!?]*){1,5})\1{4,}$',
            text, flags=re.DOTALL
        )
        if rep_match:
            text = text[:rep_match.start()].strip()

        return text.strip()

    def _build_stop_token_ids(self) -> list:
        delimiter_strings = [
            "assistant", "user", "system",
            "<|eot_id|>", "<|end_of_turn|>", "<|im_end|>",
            "<end_of_turn>", "[/INST]", "### Human", "### Assistant",
        ]
        stop_ids = [self.tokenizer.eos_token_id]
        for s in delimiter_strings:
            ids = self.tokenizer.encode(s, add_special_tokens=False)
            if ids:
                stop_ids.append(ids[0])
        seen = set()
        unique = []
        for tid in stop_ids:
            if tid is not None and tid not in seen:
                seen.add(tid)
                unique.append(tid)
        print(f"[LTX2] Stop token IDs: {unique}")
        return unique

    def generate(
        self,
        bypass, user_input, creativity, seed, invent_dialogue,
        keep_model_loaded, offline_mode, frame_count, model,
        local_path_8b, local_path_3b,
        style_preset="None — let the LLM decide",
        portrait_mode=False,
        scene_context="",
        lora_triggers="",
        use_scene_context=True,
    ):
        # ── Bypass mode ──────────────────────────────────────────────────────
        if bypass:
            print("[LTX2] Bypass ON — skipping model, passing user_input directly.")
            if self.model is not None and not keep_model_loaded:
                print("[LTX2] Bypass: cleaning up leftover model from cancelled run.")
                self.unload_model()
            neg_prompt = _build_negative_prompt("", user_input, is_portrait=portrait_mode, style_preset=style_preset)
            fps = self.PRESET_FPS.get(style_preset, 24)
            if portrait_mode and fps == 24:  # FIX: portrait always 30fps
                fps = 30
            return (user_input.strip(), user_input.strip(), neg_prompt, fps, "")

        # ── Pre-run VRAM clear — always runs before loading anything ────────────
        # Clears whatever the previous cancelled/completed video generation left
        # behind. Runs unconditionally so the LLM never loads on top of stale VRAM.
        if self.model is not None and self.loaded_model_key != model:
            print(f"[LTX2] Model mismatch — unloading stale model before reload.")
            self.unload_model()

        # Tell ComfyUI to release any models IT is holding before we load the LLM
        # This is the key step — clears the LTX video model from VRAM first
        try:
            import comfy.model_management as mm
            mm.unload_all_models()
            mm.soft_empty_cache()
            print("[LTX2] Pre-run: ComfyUI models unloaded.")
        except Exception as e:
            print(f"[LTX2] Pre-run mm call skipped: {e}")

        if torch.cuda.is_available():
            try:
                gc.collect()
                gc.collect()
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.empty_cache()
                allocated_gb = torch.cuda.memory_allocated() / 1024**3
                reserved_gb  = torch.cuda.memory_reserved()  / 1024**3
                print(f"[LTX2] Pre-run VRAM: {allocated_gb:.2f}GB allocated / {reserved_gb:.2f}GB reserved")
            except Exception as e:
                print(f"[LTX2] Pre-run CUDA flush warning: {e}")

        path_map = {
            "8B - NeuralDaredevil (High Quality)": local_path_8b,
            "3B - Llama-3.2 Abliterated (Low VRAM)": local_path_3b,
        }
        local_path = path_map.get(model, "")
        self.load_model(model_key=model, offline_mode=offline_mode, local_path=local_path)

        # ── Style preset + portrait ───────────────────────────────────────────
        preset_data            = self.STYLE_PRESETS.get(style_preset, ("", False))
        style_instruction_text = preset_data[0]
        is_portrait            = portrait_mode or preset_data[1]

        # FIX: PRESET_STYLE_LABEL moved to class-level constant — use self.PRESET_STYLE_LABEL
        style_label = self.PRESET_STYLE_LABEL.get(style_preset, "")

        if style_instruction_text:
            style_instruction = (
                f"\n[STYLE INSTRUCTION — MANDATORY AESTHETIC ANCHOR: {style_instruction_text} "
                f"Every aspect of the output — lighting, camera, colour, pacing, mood — must reflect this style. "
                f"CRITICAL: You MUST begin your output with exactly these words: \"{style_label}\" — "
                f"then continue with the scene description. This label must be the very first words of your output "
                f"so the video model knows what render style to use. Do not deviate from this style.]"
            )
            print(f"[LTX2] Style preset: {style_preset} → label: {style_label}")
        else:
            style_instruction = ""

        if is_portrait:
            portrait_instruction = (
                "\n[PORTRAIT MODE — MANDATORY: This is a 9:16 vertical video for mobile. "
                "All framing must be vertical — tight head-to-torso shots. "
                "No wide horizontal establishing shots. Action moves vertically in frame. "
                "Camera stays close. Optimised for TikTok, Reels, Shorts.]"
            )
            print("[LTX2] Portrait mode ON")
        else:
            portrait_instruction = ""

        self._last_portrait = is_portrait
        self._last_style    = style_preset

        # ── Timing & pacing ───────────────────────────────────────────────────
        real_seconds = frame_count / 24.0
        # FIX: was round(real_seconds / 4) — too conservative for LTX-2.3 which handles layered actions.
        # Now ~1 action per 3 seconds, ceiling raised to 12 for long clips.
        action_count = max(1, min(12, round(real_seconds / 3)))

        if action_count == 1:
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
                f"Dialogue is woven into action beats — it does not consume a beat and does not replace physical action. "
                f"HARD STOP after the {ordinal} action is complete. The scene ends there. Do not write a {action_count + 1}th action under any circumstances."
            )

        # ── Seed ──────────────────────────────────────────────────────────────
        if seed != -1:
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)

        # ── Dynamic token budget ─────────────────────────────────────────────
        # LTX-2.3 text encoder effectively uses ~200 words max.
        # Anything beyond 500 words is wasted — the model ignores the tail.
        # Target scales with clip length but is hard-capped at 500.
        # The LLM generation ceiling is 2x the target so it never clips mid-sentence.
        LTX_WORD_FLOOR   = 150   # minimum — enough detail for any clip
        LTX_WORD_CEILING = 500   # hard cap — LTX-2.3 doesn't use beyond this

        # FIX: was action_count * 80 + 100 — too thin for blocking + textures + sound + dialogue.
        # Now action_count * 100 + 150 gives richer prompts, still within LTX-2.3's effective window.
        token_val         = max(LTX_WORD_FLOOR, min(LTX_WORD_CEILING, action_count * 100 + 150))
        max_tokens_actual = token_val * 2    # LLM hard stop — always 2x target so it finishes
        # FIX: removed min_new_tokens — it forced the model to continue past natural stop points,
        # causing hallucinated paragraphs. Let stop token IDs and max_new_tokens handle termination.
        print(f"[LTX2] Token budget: {token_val} words target / {max_tokens_actual} LLM max (actions={action_count}, {real_seconds:.0f}s)")

        # ── Temperature ───────────────────────────────────────────────────────
        temp_map = {
            "0.5 - Strict & Literal":      0.5,
            "0.8 - Balanced Professional": 0.8,
            "1.0 - Artistic Expansion":    1.0,
        }
        temperature = temp_map[creativity]

        # FIX: stop token IDs are now cached at model load time — no need to rebuild each call
        stop_token_ids = self._stop_token_ids

        # ── Content tier detection ────────────────────────────────────────────
        _explicit_re = re.compile(
            r"\b(pussy|cock|dick|penis|vagina|clit|clitoris|anus|asshole|"
            r"tits|cum|orgasm|fuck|fucking|blowjob|handjob|penetrat\w*|"
            r"thrust\w*)\b",
            re.IGNORECASE,
        )
        # FIX: _undress_re defined first; _sensual_re built as superset to eliminate duplication.
        # Previously both contained the full undressing verb list — any edit required two identical changes.
        _undress_core = (
            r"undress\w*|strip\w*|takes?\s+off|"
            r"removes?\s+(her|his|their|the)?\s*\w*\s*"
            r"(shirt|dress|top|bra|pants|jeans|clothes|clothing|outfit|underwear|skirt|jacket|coat|robe)|"
            r"disrobe\w*|unbutton\w*|unzip\w*|peels?\s+off|pulls?\s+off|"
            r"shed\w*\s+(her|his|their)?\s*(clothes|clothing|shirt|dress)|"
            r"lift\w*\s+(her|his|their|the)?\s*(shirt|top|dress|skirt|crop|tee|t-shirt)|"
            r"(shirt|top|dress|skirt|crop|tee|t-shirt)\s+(up|lifted|raised|hiked)|"
            r"flash\w*\s+(her|his|their)?\s*(breasts?|chest|tits?|boobs?)|"
            r"hik\w*\s+(her|his|their|the)?\s*(shirt|top|skirt|dress)"
        )
        _undress_re = re.compile(r"\b(" + _undress_core + r")\b", re.IGNORECASE)
        _sensual_re = re.compile(
            r"\b(" + _undress_core + r"|"
            r"naked|nude|topless|"
            r"sensual|erotic|intimate|lingerie|bare\s+skin|bare\s+body|"
            r"babydoll|nighty|nightie|negligee|corset|bodysuit|thong|g-string|"
            r"sheer|see-through|tease|teasing|seductive|seduce|"
            r"flirt\w*|provocative|suggestive|alluring)\b",
            re.IGNORECASE,
        )
        # Detect lift/flash specifically — partial reveal, not full removal
        _lift_re = re.compile(
            r"\b(lift\w*\s+(her|his|their|the)?\s*(shirt|top|dress|skirt|crop|tee|t-shirt)|"
            r"(shirt|top|dress|skirt|crop|tee|t-shirt)\s+(up|lifted|raised|hiked)|"
            r"flash\w*\s+(her|his|their)?\s*(breasts?|chest|tits?|boobs?)|"
            r"hik\w*\s+(her|his|their|the)?\s*(shirt|top|skirt|dress))\b",
            re.IGNORECASE,
        )

        # FIX: all content-tier detections now include scene_context — vision node descriptions
        # of nudity, undressing, or sensual content must be picked up here, not silently ignored.
        _active_scene_context = scene_context if use_scene_context else ""
        _combined_input = user_input + " " + _active_scene_context
        is_explicit    = bool(_explicit_re.search(_combined_input))
        is_sensual     = bool(_sensual_re.search(_combined_input)) and not is_explicit
        has_undressing = bool(_undress_re.search(_combined_input))
        has_lift       = bool(_lift_re.search(_combined_input))

        # ── Detect exactly which garments the user named ──────────────────────
        _garment_re = re.compile(
            r"\b(shirt|top|blouse|dress|bra|pants|jeans|underwear|skirt|jacket|"
            r"coat|robe|lingerie|clothes|clothing|outfit|thong|g-string|bodysuit|"
            r"corset|nighty|nightie|negligee|babydoll)\b",
            re.IGNORECASE,
        )
        named_garments = list(dict.fromkeys(
            m.group(0).lower() for m in _garment_re.finditer(_combined_input)
        ))
        garment_list = ", ".join(named_garments) if named_garments else "whatever the user described"

        if is_explicit:
            explicit_instruction = (
                "\n[CONTENT INSTRUCTION — EXPLICIT ADULT SCENE: "
                "Use direct anatomical language exactly as the user wrote it. "
                "If they said 'pussy' write 'pussy'. If they said 'cock' write 'cock'. Never substitute euphemisms like 'womanhood', 'manhood', 'core', or 'sex'. "
                "\n\nCAMERA & LENS — MANDATORY even in explicit scenes: always include focal length and aperture: "
                "'85mm f/1.4', '50mm f/2.0', '35mm f/2.8'. Always add: natural motion blur, 180 degree shutter equivalent. "
                "Avoid high frequency patterns in any surface, fabric, or background — these cause flickering. "
                "\n\nSCOPE — ABSOLUTE CEILING: "
                "Describe ONLY what the user explicitly wrote. Nothing beyond. "
                "Do NOT add sexual acts, nudity, or body exposure the user did not state. "
                "One garment requested = one garment removed. Undressing only = describe undressing only. "
                "Do NOT improvise the next logical step. The scene ends where the user's words end. "
                "\n\nSOUND IS MANDATORY: Every scene must have sound — breathing, fabric, footsteps, environment, whatever fits. "
                "Do not write a silent scene under any circumstances. "
                f"\n\nUNDRESSING SEQUENCE — the user's garments are: {garment_list}. "
                "Write a dedicated undressing segment BEFORE any nudity. One sentence per step. Camera lingers on each reveal. "
                "T-shirt/shirt/crop top (full off): grip hem at waist → lift past stomach → past ribs → over chest → over head → off arms → dropped. "
                "T-shirt/shirt/crop top (lift only): grip hem → gather upward → rises past stomach → past navel → past ribs → chest and breasts fully exposed → held there. One step per sentence. "
                "Dress (zip): reach behind → find zip → pull slowly down → fabric parts → slipped off shoulders → slides down → falls. "
                "Dress (pullover): grip hem at thighs → over hips → over waist → over chest → over head → gone. "
                "Blouse/button-down: each button one at a time → fabric parts → off shoulders → down arms → dropped. "
                "Bra: clasp behind → unhooked → straps off each shoulder → cups fall away. "
                "Jeans/trousers: button → zip → pushed over hips → down thighs → stepped out. "
                "Underwear: thumbs in waistband → pushed down → stepped out. "
                "NO INVENTED RESOLUTION: what goes up stays up. Do not reverse, cover, or undo any action unless the user asked for it. "
                "Always state character age as a specific number.]"
            )
        elif is_sensual:
            if has_undressing:
                undress_clause = (
                    f"\n\nUNDRESSING — SCOPE CEILING: User named these garments only: {garment_list}. "
                    f"Remove ONLY those. Nothing beyond. "
                    f"Do NOT advance from shirt → bra unless user said bra. "
                    f"Do NOT advance from bra → topless unless user said topless or nude. "
                    f"Do NOT advance from clothing → underwear unless user said underwear. "
                    f"Do NOT advance from underwear → nudity unless user said nude or naked. "
                    f"The named garments are the ceiling. Style preset does NOT override this. "
                    f"\n\nSOUND IS MANDATORY throughout — fabric sounds, breathing, environment. Never silent. "
                    f"\n\nFor each garment write every physical step as its own sentence: "
                    f"T-shirt/shirt/crop top (full off): grip hem at waist → lift past stomach → past ribs → over chest → over head → off arms → dropped. "
                    f"T-shirt/shirt/crop top (lift only): grip hem → gather upward → rises past stomach → past navel → past ribs → chest fully exposed → held there. One step per sentence. "
                    f"Dress (zip): find zip behind → pull slowly down → fabric parts → off shoulders → slides down → falls. "
                    f"Dress (pullover): grip hem at thighs → over hips → over waist → over chest → over head. "
                    f"Blouse/button-down: each button top to bottom → fabric parts → off shoulders → down arms. "
                    f"Bra: clasp behind → unhook → straps off each shoulder → cups fall away. "
                    f"Jeans/trousers: button → zip → over hips → down thighs → stepped out. "
                    f"Underwear: thumbs in waistband → pushed down → stepped out. "
                    f"Camera holds on each reveal. STOP after the last named garment. "
                    f"NO INVENTED RESOLUTION: do not reverse or cover any action unless the user asked. "
                    f"Bare skin described naturally — genitals not described unless user used explicit terms."
                )
            else:
                undress_clause = (
                    "\n\nNO UNDRESSING: User has not asked for clothing removal. "
                    "Do NOT remove, loosen, or sexualise any clothing. "
                    "Do NOT describe underwear, bare skin below the neck, or implied nudity. "
                    "Stay exactly at the level of sensuality the user described — no further. "
                    "\n\nSOUND IS MANDATORY — environment, clothing movement, breathing, whatever fits. Never silent."
                )
            explicit_instruction = (
                "\n[CONTENT INSTRUCTION — SENSUAL SCENE: "
                "Tone: warm, cinematic, tasteful. "
                "SCOPE — ABSOLUTE CEILING: Describe ONLY what the user asked for. Do NOT self-escalate. "
                "Do NOT invent undressing, nudity, or acts the user did not write. "
                "Style preset controls aesthetics only — it does NOT give permission to add content. "
                "SOUND IS MANDATORY: every beat needs sound — fabric, breathing, environment. Never silent. "
                "Always state character age as a specific number. "
                + undress_clause + "]"
            )
        else:
            explicit_instruction = (
                "\n[INSTRUCTION — CINEMATIC LTX-2.3 PROMPT: "
                "LTX-2.3 handles complexity well — be specific, do not simplify. "
                "Build the prompt in this order: "
                "(1) Style and genre. Where it fits, weave a film stock or camera reference into prose naturally — "
                "e.g. 'carries a Kodak 2383 warmth', 'ARRI Alexa clean look', 'Fuji Eterna flat shadows'. "
                "NEVER output as a bracketed tag like [Kodak 5219] — must be prose, not a label. "
                "(2) Shot type and camera angle with MANDATORY lens spec every time: "
                "'85mm f/1.4', '35mm f/2.8', '50mm anamorphic f/2.0', '24mm wide f/4'. "
                "Always add: natural motion blur, 180 degree shutter equivalent — non-negotiable in every output. "
                "CRITICAL: Weave lens and shutter INTO the prose — NEVER as a labelled ending like 'Lens: 50mm f/2.0' or 'Camera angle: close-up' appended at the end. "
                "(3) Character — age as a number always, default 18–35 unless input implies older/younger. "
                "Use 40+ only if user says older/mature/elderly. Use under-18 only if context is explicitly school/teen — never for sexual content. "
                "Hair texture and colour, skin tone, body type, "
                "clothing with fabric and material detail: 'a fitted black cotton crop top', not just 'a top'. "
                "Include subtle micro expressions and emotional cues: 'the corners of her lips tighten slightly', "
                "'her eyes lose focus for a moment', 'a faint tension forms across her jaw'. These create life. "
                "(4) Spatial blocking — explicit left/right/fore/background, who faces what, distances stated. "
                "(5) Environment — location, lighting direction, surface textures. "
                "CRITICAL: avoid high frequency patterns in clothing, walls, floors, and backgrounds — "
                "fine stripes, tight grids, detailed fabric weaves cause flickering artifacts. "
                "Favour solid colours, simple textures, smooth surfaces. "
                "(6) Action — VERBS: who moves, what moves, how, what the camera does simultaneously. "
                "For smooth motion: stable dolly movement, smooth gimbal tracking, constant speed pan, controlled camera path. "
                "If static, add ONE environmental motion: a camera drift, wind in hair, a background figure passing. "
                "(7) Texture in motion — how materials behave as things move: fabric pulling, hair lifting, skin catching light. "
                "(8) Camera movement — prose verbs: 'the shot pushes in slowly', never bracketed. "
                "Vocabulary: dolly in/out, rack focus, slow orbit, stabilised gimbal arc, creep forward, track right. "
                "(9) Sound — MANDATORY, physical and concrete, max 2 per beat, tone and intensity. "
                "When sound and action are synchronised state the timing: 'on the downbeat', 'precisely as the hand lands'. "
                "Music/dance scenes: describe the music as physical sound — beat, bass, tempo, texture. Never silent.]"
            )

        # ── Camera orientation detection ──────────────────────────────────────
        # Only fires when the user EXPLICITLY asks for rear/behind framing.
        # Default is front-facing — do NOT infer rear view from walking or movement alone.
        _facing_away_re = re.compile(
            r"\b(from behind|from the back|rear.?view|back.?view|"
            r"camera behind|shoot(ing)? from behind|filmed? from behind|"
            r"watches? (her|him|them) from behind|follows? (her|him|them) from behind|"
            r"camera follows? (her|him|them)|follow(ing)? her from behind|"
            r"over.{0,6}shoulder from behind|back of (her|his|their) head)\b",
            re.IGNORECASE,
        )
        _facing_camera_re = re.compile(
            r"\b(faces? (the )?camera|looks? (at|into) (the )?camera|"
            r"faces? forward|toward (the )?camera|facing (us|viewer|audience)|"
            r"selfie|mirror selfie|talking to camera|front.?facing|facing front)\b",
            re.IGNORECASE,
        )
        is_facing_away   = bool(_facing_away_re.search(_combined_input))
        is_facing_camera = bool(_facing_camera_re.search(_combined_input))

        # Voyeur preset: rear-facing unless user explicitly said facing camera
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
                " Open your output with the orientation stated clearly — e.g. 'Rear view.' or 'The camera follows from behind.' "
                "No front-facing shots. No face visible. Rear view for the entire scene.]"
            )
        else:
            orientation_instruction = ""

        # ── Sequence detection ────────────────────────────────────────────────
        _sequence_re = re.compile(r"^\s*(\d+[\.\):])\s+.+", re.MULTILINE)
        sequence_steps = _sequence_re.findall(_combined_input)
        if len(sequence_steps) >= 2:
            step_count = len(sequence_steps)
            sequence_instruction = (
                f"\n[SEQUENCE INSTRUCTION: The user has provided {step_count} numbered steps. "
                f"You MUST follow them in exact order — step 1 first, then step 2, and so on. "
                f"Do not reorder, skip, or merge steps. Each step is one distinct beat in the scene. "
                f"Do not add actions before step 1 or after step {step_count}.]"
            )
        else:
            sequence_instruction = ""

        # ── Anti-static detection ─────────────────────────────────────────────
        # LTX-2.3 produces freeze frames from static prompts. Detect inputs that
        # describe a pose/state with no motion and inject a motion reminder.
        _motion_re = re.compile(
            r"\b(walk\w*|run\w*|mov\w*|turn\w*|lift\w*|bend\w*|reach\w*|pull\w*|push\w*|"
            r"danc\w*|jump\w*|climb\w*|fall\w*|drop\w*|sit\w*|stand\w*|rise\w*|lean\w*|"
            r"nod\w*|shak\w*|wave\w*|stir\w*|pour\w*|open\w*|clos\w*|look\w*|glanc\w*|"
            r"strip\w*|undress\w*|remov\w*|lift\w*|hike\w*|unzip\w*|unbutton\w*|"
            r"crawl\w*|kneel\w*|stretch\w*|sway\w*|bounce\w*|grind\w*|thrust\w*|"
            r"follows?|tracking|panning|dolly|zoom\w*|tilt\w*|orbit\w*|drift\w*)\b",
            re.IGNORECASE,
        )
        has_motion = bool(_motion_re.search(_combined_input))
        if not has_motion:
            static_instruction = (
                "\n\n[MOTION INSTRUCTION: The user's input has no explicit motion verbs. "
                "Add directed movement — camera first: a slow push in, a gentle track, a creeping orbit. "
                "Then one subject action if it fits: a head turn, a step forward, a glance to the side. "
                "Only if neither applies, add a single environmental detail: wind moving hair, a background figure passing. "
                "Do not stack micro-movements. One well-directed motion beats five passive ones. "
                "LTX-2.3 holds complex motion — use verbs of progression, not filler.]"
            )
        else:
            static_instruction = ""

        # ── Person detection ──────────────────────────────────────────────────
        _person_re = re.compile(
            r"\b(he|she|his|her|him|they|them|their|man|men|woman|women|girl|girls|boy|boys|guy|guys|"
            r"person|people|couple|figure|character|model|actress|actor|"
            r"someone|anybody|nobody|stranger|friend|lover|wife|husband|"
            r"boyfriend|girlfriend|teenager|teenagers|adult|adults|female|male|blonde|brunette|"
            r"redhead|nude|naked|singer|dancer|performer|athlete|soldier|worker|"
            r"player|nurse|doctor|student|teacher|child|children|kid|kids|crowd|audience)\b",
            re.IGNORECASE,
        )
        has_person = bool(_person_re.search(user_input + " " + scene_context))
        if not has_person:
            no_person_instruction = (
                "\n[SCENE INSTRUCTION: No person or character in this scene. "
                "Do NOT invent human figures, silhouettes, voices, or implied presence. "
                "Write only the setting, objects, light, and motion of non-human elements. "
                "No characters, no 'someone', no implied human presence. No dialogue or voices. "
                "SOUND IS STILL MANDATORY: describe environmental sound — wind, water, machinery, rain, "
                "animals, structural sounds — whatever physically fits the scene. Never silent.]"
            )
        else:
            no_person_instruction = ""

        # ── Multi-subject detection ───────────────────────────────────────────
        _multi_re = re.compile(
            r"\b(two\s+(women|men|people|girls|guys|characters|figures|friends|strangers|colleagues|lovers|siblings|brothers|sisters)|"
            r"both\s+(of\s+them|women|men|girls|guys)|"
            r"(she|he)\s+and\s+(she|he|her|him)|"
            r"(a\s+man\s+and\s+a\s+woman|a\s+woman\s+and\s+a\s+man)|"
            r"(a\s+man\s+and\s+a\s+man|a\s+woman\s+and\s+a\s+woman)|"
            r"couple|trio|they\s+(kiss|touch|embrace|undress|fuck|have))\b",
            re.IGNORECASE,
        )
        has_multi_subject = bool(_multi_re.search(user_input + " " + scene_context))
        if has_multi_subject:
            multi_instruction = (
                "\n[MULTI-SUBJECT INSTRUCTION: This scene has two or more people. "
                "For EACH person establish: their position in the frame (left/right/foreground/background), "
                "their spatial relationship to the other person (facing, beside, behind, above, etc.), "
                "and keep track of who is doing what throughout — never let actions become ambiguous. "
                "When referring back to them use consistent descriptors (e.g. 'the dark-haired woman', "
                "'the taller man') — not just 'she' or 'he' which causes confusion with two subjects.]"
            )
        else:
            multi_instruction = ""

        # ── Music / dance detection ───────────────────────────────────────────
        # When user mentions music, dancing, or a beat-driven scene, the "no musical audio"
        # rule must not suppress music description. Detect and override.
        _music_re = re.compile(
            r"\b(music|song|track|beat|bass|rhythm|danc\w*|club|rave|party|dj|"
            r"playlist|bpm|groove|vibe|concert|gig|perform\w*|sing\w*|singer|"
            r"strip\w*club|pole danc\w*|lap danc\w*)\b",
            re.IGNORECASE,
        )
        has_music = bool(_music_re.search(_combined_input))

        if has_music:
            music_sound_rule = (
                "SOUND — MUSIC SCENE: Describe the music as physical sensation and sound. "
                "Not 'music plays' — give it body: 'a deep kick drum at 128bpm punches through the floor, sub-bass felt in the chest', "
                "'sharp hi-hats tick over a slow rolling groove', 'the mix drops into a swell of layered synths', "
                "'a warm bass line pulses under the melody'. "
                "Describe tempo, weight, texture, and what it feels like in the space. "
                "Max 2 additional sounds alongside the music (crowd noise, heels on floor, breathing). "
                "Do NOT silence the music. Do NOT reduce it to a label."
            )
        else:
            music_sound_rule = (
                "SOUND — describe with tone, intensity, and environment. "
                "Not 'footsteps' — 'the sharp rhythmic clack of heels on cold tile, each step clean and even'. "
                "Not 'rain' — 'rain striking the glass in irregular bursts, a low persistent hiss beneath it'. "
                "Max 2 sounds active per beat. No abstract emotional audio — no 'tension fills the air', "
                "no 'heartbeat of the city'. Physical sound only, described fully."
            )

        # ── Dialogue instruction ──────────────────────────────────────────────
        if not has_person:
            dialogue_instruction = ""
        elif invent_dialogue:
            dialogue_instruction = (
                "\n\n[DIALOGUE INSTRUCTION — MANDATORY, CANNOT BE SKIPPED: "
                "You MUST include at least one line of spoken dialogue in this scene. "
                "An output with zero spoken words has failed this instruction. "
                "Invent dialogue that sounds like something a real person would actually say in this exact situation — not a cliché. "
                "Write it as inline prose woven into the action, with attribution and physical delivery, like a novel. "
                "The spoken words sit inside the sentence — never as a floating quote, never as a [DIALOGUE: ...] tag. "
                "Examples: "
                "'\"Don\\'t stop,\" she breathes, gripping the sheets, her voice barely above a whisper.' "
                "'She glances back, \"Are you watching me?\" her tone half-amused, half-serious.' "
                "'\"Come here,\" he says quietly, his hand extended.' "
                "If the scene is sexual or explicit, dialogue must reflect that — breathless, reactive, direct. "
                "Weave it into a physical beat — the character speaks while doing something, not in a static pause. "
                + music_sound_rule + "]"
            )
        else:
            has_user_dialogue = bool(re.search(r'["\u201c\u201d]', user_input))
            if has_user_dialogue:
                dialogue_instruction = (
                    "\n\n[DIALOGUE INSTRUCTION: Use ONLY the dialogue the user provided — do not invent or add any additional spoken words. "
                    "Place their exact words naturally in the scene as inline prose with attribution and delivery. "
                    "Examples: 'She smiles, \"I\\'m so happy,\" her voice bright, eyes wide.' "
                    "Never use [DIALOGUE: ...] tags. Weave the words into the action as part of the prose.]"
                )
            else:
                dialogue_instruction = (
                    "\n\n[DIALOGUE INSTRUCTION: No dialogue in this scene. No spoken words. "
                    "Weave sound naturally into the prose instead — described as prose, not tags. "
                    + music_sound_rule + "]"
                )

        # ── Length instruction ────────────────────────────────────────────────
        length_instruction = (
            f"\n[PACING: {pacing_hint} "
            f"Aim for approximately {token_val} words of prose. "
            f"Do not exceed the action count above. "
            f"Output ends with the final sentence of the scene — no summaries, no counts, no notes, no brackets after the last word.]"
        )

        # ── Lift / flash instruction — fires when a shirt lift or flash is detected ──
        if has_lift:
            lift_instruction = (
                "\n\n[SHIRT LIFT SEQUENCE — MANDATORY, one sentence per step, do not compress: "
                "1. Her fingers find the hem at the waist. "
                "2. She grips the fabric and begins gathering it upward. "
                "3. The shirt rises past her stomach. "
                "4. The fabric passes her navel, exposing her bare midriff. "
                "5. The shirt climbs past her ribs. "
                "6. Her chest comes into view. "
                "7. Her breasts are fully exposed, the shirt held up. "
                "The shirt STAYS LIFTED. Do NOT write her lowering it or covering herself unless asked. "
                "SOUND during the lift: describe the soft friction of fabric, her breathing, whatever fits the scene.]"
            )
        else:
            lift_instruction = ""

        # ── Character seed ────────────────────────────────────────────────────
        # Suppress the seed entirely if the user has already described their character.
        # A seed is only useful when the user gave NO appearance info — it fills the gap.
        # If the user wrote age, hair, skin, clothing, or body details, the seed fights them
        # and wins because it is more specific and positioned last. Suppress it instead.
        _user_described_character = bool(re.search(
            r'\b(\d{1,2})[- ]?year[- ]?old\b'  # explicit age number
            r'|\b(blonde|brunette|redhead|black hair|brown hair|dark hair|grey hair|gray hair'
            r'|silver hair|auburn|curly|straight|wavy|afro|braids|pixie|bob|long hair|short hair)\b'
            r'|\b(pale|fair|light|dark|brown|black|tan|olive|caramel|ebony|ivory) skin\b'
            r'|\b(slim|petite|curvy|full.figured|athletic|muscular|stocky|plus.size|thick)\b'
            r'|\b(wearing|dressed in|clad in|in a|in her|in his)\b'
            r'|\b(dress|skirt|jeans|trousers|shirt|blouse|top|coat|jacket|pyjamas|nighty|nightgown|lingerie|underwear|bra|panties)\b',
            user_input, re.IGNORECASE
        ))

        if has_person and not _user_described_character:
            rng = random.Random(seed if seed != -1 else None)
            char_description = _build_char_seed(rng)
            char_seed_note = (
                f"\n[CHARACTER SEED: {char_description}. "
                f"Use this as your character foundation. Add clothing with exact fabric and material appropriate to the scene.]"
            )
        else:
            char_seed_note = ""
            if has_person and _user_described_character:
                print("[LTX2] User described character — seed suppressed. Using input as character source.")

        # ── Vision context ────────────────────────────────────────────────────
        # FIX: char_seed_note is suppressed when scene_context is present.
        # Previously the random character seed was always appended after effective_input,
        # so the LLM was told "use the image as authority" then immediately given a
        # contradicting invented character (different clothes, hair, skin) — the seed won
        # because it was more specific and came last. When an image is wired in, the
        # image description IS the character. No seed needed or wanted.
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
            # char_seed_note intentionally NOT appended — the image is the character
        else:
            effective_input = user_input.strip()
            if has_person and _user_described_character:
                effective_input += (
                    "\n[CHARACTER NOTE: The user has described the character's appearance. "
                    "Use ONLY the user's description for all visual details — age, hair, skin, clothing, body. "
                    "Do NOT invent or substitute any appearance detail not present in the input above.]"
                )
            effective_input += char_seed_note

        # ── LoRA triggers ─────────────────────────────────────────────────────
        # We no longer ask the LLM to prepend triggers — it mangles them with
        # style label text. Instead: tell LLM to skip the trigger entirely,
        # and we hard-prepend it in post-processing after _clean_output.
        if lora_triggers and lora_triggers.strip():
            lora_instruction = (
                f"\n[LORA NOTE: LoRA trigger words will be prepended automatically. "
                f"Do NOT include them in your output. Start directly with the style label or scene description.]"
            )
        else:
            lora_instruction = ""

        # ── Build messages ────────────────────────────────────────────────────
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user",   "content": (
                effective_input
                # FIX: lora_instruction moved here — immediately after input, before all style/portrait
                # instructions. Late-position LoRA instructions were being ignored by 3B models on
                # long prompts. Trigger words must be seen early to be reliably injected at output start.
                + lora_instruction
                + orientation_instruction
                + style_instruction
                + portrait_instruction
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

        raw = self.tokenizer.apply_chat_template(
            messages,
            return_tensors="pt",
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

        # ── Generation — wrapped so cancelled runs always unload ──────────────
        try:
            with torch.no_grad():
                output_ids = self.model.generate(
                    input_ids,
                    # FIX: min_new_tokens removed — was forcing continuation past natural stop points,
                    # causing hallucinated extra paragraphs. max_new_tokens + eos_token_id handle termination.
                    max_new_tokens=max_tokens_actual,
                    temperature=temperature,
                    do_sample=True,
                    top_k=40,
                    top_p=0.9,
                    repetition_penalty=1.07,
                    use_cache=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=stop_token_ids,
                )
        except Exception as _gen_exc:
            # Generation cancelled or errored — unload immediately so next run
            # doesn't find a half-dead model occupying VRAM
            print(f"[LTX2] Generation interrupted: {_gen_exc}")
            print("[LTX2] Forcing unload due to interrupted generation.")
            self.unload_model()
            raise

        generated_tokens = output_ids[0][input_length:]
        result = self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

        del generated_tokens
        del output_ids
        del input_ids
        gc.collect()

        result = self._clean_output(result)

        # Clear KV cache from model state — generate() leaves past_key_values
        # in model memory if use_cache=True, growing with each run
        if self.model is not None:
            try:
                if hasattr(self.model, "past_key_values"):
                    self.model.past_key_values = None
            except Exception:
                pass

        # ── LoRA trigger hard prepend ─────────────────────────────────────────
        # Always prepend trigger words here — LLM is told NOT to include them
        # so we guarantee they are the very first tokens, clean and unmangled.
        if lora_triggers and lora_triggers.strip():
            triggers = lora_triggers.strip()
            # Strip any leaked trigger words the LLM may have included anyway
            if result.lower().startswith(triggers.lower()):
                result = result[len(triggers):].lstrip(" ,—-")
            result = triggers + ", " + result
            print(f"[LTX2] LoRA triggers prepended: {triggers}")

        # ── Style label safety net ────────────────────────────────────────────
        # If the LLM forgot to open with the style label, prepend it now
        # so LTX-2's text encoder always sees the render style
        if style_label and not result.lower().startswith(style_label.split()[0].lower()):
            result = style_label + " " + result
            print(f"[LTX2] Style label prepended (LLM omitted it): {style_label}")

        neg_prompt = _build_negative_prompt(
            result, user_input,
            is_portrait=self._last_portrait,
            style_preset=self._last_style,
        )

        # ── Prompt history ────────────────────────────────────────────────────
        # Saves last 20 runs to prompt_history.json next to this script
        # Also builds a HISTORY string for the output pin (last 5 runs)
        history_string = ""
        try:
            _hist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt_history.json")
            _history = []
            _first_save = not os.path.exists(_hist_path)
            if not _first_save:
                with open(_hist_path, "r", encoding="utf-8") as _f:
                    _history = json.load(_f)
            _history.insert(0, {
                "timestamp": _time.strftime("%Y-%m-%d %H:%M:%S"),
                "style":     style_preset,
                "portrait":  is_portrait,
                "input":     user_input[:300],
                "output":    result[:800],
            })
            _history = _history[:20]
            with open(_hist_path, "w", encoding="utf-8") as _f:
                json.dump(_history, _f, indent=2, ensure_ascii=False)

            if _first_save:
                print(f"[LTX2] Prompt history file created at: {_hist_path}")
            else:
                print(f"[LTX2] Prompt history saved ({len(_history)} runs) → {_hist_path}")

            # Build the HISTORY output pin — last 5 runs as readable text
            lines = []
            for i, entry in enumerate(_history[:5], 1):
                lines.append(
                    f"── Run {i}  [{entry['timestamp']}]  {entry['style']}\n"
                    f"IN:  {entry['input'][:120]}\n"
                    f"OUT: {entry['output'][:300]}"
                )
            history_string = "\n\n".join(lines)

        except Exception as _he:
            print(f"[LTX2] Prompt history save failed (non-fatal): {_he}")
            history_string = f"[History unavailable: {_he}]"

        # Clear tokenizer internal cache every run — fast tokenizers cache encoded
        # strings in system RAM. With keep_model_loaded=True this grows run after run.
        if self.tokenizer is not None:
            try:
                # PreTrainedTokenizerFast holds a Rust-backed cache — clear it
                if hasattr(self.tokenizer, "_tokenizer"):
                    # The underlying Rust tokenizer has no direct clear, but
                    # clearing the Python-side vocab cache is what we can reach
                    pass
                # The encode cache lives on the Python wrapper side
                if hasattr(self.tokenizer, "cache"):
                    self.tokenizer.cache.clear()
                # Also clear the added_tokens encode cache if present
                if hasattr(self.tokenizer, "_added_tokens_encoder"):
                    self.tokenizer._added_tokens_encoder.clear()
                    self.tokenizer._added_tokens_decoder.clear()
            except Exception as _tc:
                pass  # Non-fatal — just means cache persists this run
            gc.collect()

        if not keep_model_loaded:
            self.unload_model()

        fps = self.PRESET_FPS.get(style_preset, 24)
        # FIX: when portrait_mode=True is set manually (not via Portrait preset), the cinematic
        # preset may return 24fps. Portrait content (TikTok/Reels/Shorts) expects 30fps.
        if is_portrait and fps == 24:
            fps = 30
        print(f"[LTX2] FPS output: {fps}  (preset: {style_preset}, portrait: {is_portrait})")

        return (result, result, neg_prompt, fps, history_string)


# ── ComfyUI boilerplate ──────────────────────────────────────────────────────

class LTX2UnloadModel:
    """Utility node to manually free VRAM when keep_model_loaded is True."""

    @classmethod
    def INPUT_TYPES(s):
        return {"required": {}}

    RETURN_TYPES = ()
    FUNCTION = "unload"
    CATEGORY = "LTX2"
    OUTPUT_NODE = True

    def unload(self):
        import gc
        unloaded = 0
        for obj in gc.get_objects():
            if isinstance(obj, LTX2PromptArchitect) and obj.model is not None:
                obj.unload_model()
                unloaded += 1
        print(f"[LTX2] Unload node: freed {unloaded} model instance(s).")
        return {}


NODE_CLASS_MAPPINGS = {
    "LTX2PromptArchitect": LTX2PromptArchitect,
    "LTX2UnloadModel":     LTX2UnloadModel,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LTX2PromptArchitect": "LTX-2.3 Easy Prompt By LoRa-Daddy",
    "LTX2UnloadModel":     "LTX2 Unload Model",
}
