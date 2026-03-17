#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小虫子提示词优化引擎
- 智能分析基础提示词
- 自动丰富细节描述
- 添加艺术风格元素
- 优化构图和灯光
- 生成专业级提示词
"""

import json
import random
from typing import Dict, List

class LittleBugOptimizer:
    """小虫子提示词优化器"""
    
    def __init__(self):
        # 详细描述库
        self.detail_library = {
            "人物": [
                "精致的五官", "细腻的皮肤纹理", "生动的表情", "自然的眼神",
                "优雅的姿势", "飘逸的头发", "微笑的嘴角", "专注的神情"
            ],
            "风景": [
                "层次分明的远山", "波光粼粼的水面", "郁郁葱葱的树木",
                "蜿蜒的小路", "飘浮的白云", "柔和的光影", "丰富的植被"
            ],
            "建筑": [
                "精美的雕花装饰", "宏伟的结构", "古典的柱式", "现代的线条",
                "透明的玻璃幕墙", "石质纹理", "金属质感", "木质细节"
            ],
            "动物": [
                "柔软的毛发", "明亮的眼睛", "生动的姿态", "自然的动作",
                "细腻的皮毛纹理", "灵动的眼神", "优雅的身姿"
            ],
            "食物": [
                "诱人的色泽", "细腻的质感", "升腾的热气", "新鲜的食材",
                "精致的摆盘", "丰富的层次", "诱人的光泽"
            ]
        }
        
        # 艺术风格库
        self.art_styles = {
            "写实": "photorealistic, ultra detailed, 8k resolution, professional photography",
            "油画": "oil painting style, textured brushstrokes, classical art, masterpiece",
            "水彩": "watercolor painting, soft edges, translucent layers, artistic",
            "动漫": "anime style, cel shading, vibrant colors, Japanese animation",
            "赛博朋克": "cyberpunk aesthetic, neon lights, high tech, futuristic",
            "奇幻": "fantasy art, magical atmosphere, epic composition, mystical",
            "印象派": "impressionist style, visible brushstrokes, play of light",
            "超现实": "surrealist art, dreamlike quality, unexpected juxtapositions"
        }
        
        # 灯光效果库
        self.lighting_effects = [
            "golden hour lighting, warm and soft",
            "dramatic side lighting, strong shadows",
            "soft diffused light, gentle atmosphere",
            "neon lighting, colorful reflections",
            "cinematic lighting, movie-like quality",
            "natural sunlight, bright and clear",
            "moonlight, cool and mysterious",
            "studio lighting, professional setup",
            "volumetric lighting, god rays",
            "rim lighting, edge highlight"
        ]
        
        # 构图技巧库
        self.composition_techniques = [
            "rule of thirds, balanced composition",
            "centered composition, symmetrical",
            "leading lines, depth perspective",
            "foreground interest, layered depth",
            "wide angle view, expansive scene",
            "close-up detail, intimate perspective",
            "bird's eye view, overhead perspective",
            "low angle shot, dramatic perspective",
            "depth of field, bokeh background",
            "panoramic view, wide scene"
        ]
        
        # 质量增强词
        self.quality_enhancers = [
            "masterpiece, best quality, ultra high quality",
            "award winning, professional grade",
            "highly detailed, intricate details",
            "photorealistic, stunning visuals",
            "exceptional quality, pristine",
            "flawless detail, crystal clear",
            "premium quality, extraordinary"
        ]
        
        # 氛围词库
        self.atmosphere_words = {
            "平静": "peaceful, serene, tranquil, calm",
            "活力": "dynamic, energetic, vibrant, lively",
            "神秘": "mysterious, enigmatic, mystical, ethereal",
            "浪漫": "romantic, dreamy, soft, intimate",
            "史诗": "epic, grand, majestic, monumental",
            "忧郁": "melancholic, moody, atmospheric, contemplative",
            "欢乐": "cheerful, joyful, bright, uplifting",
            "紧张": "tense, dramatic, intense, suspenseful"
        }
    
    def analyze_prompt(self, prompt: str) -> Dict:
        """分析提示词，识别主题和元素"""
        analysis = {
            "themes": [],
            "elements": [],
            "mood": "neutral",
            "style": "default"
        }
        
        # 关键词匹配
        prompt_lower = prompt.lower()
        
        # 识别人物
        if any(word in prompt_lower for word in ["女孩", "男孩", "人", "portrait", "face", "woman", "man"]):
            analysis["themes"].append("人物")
            analysis["elements"].append("人物主体")
        
        # 识别风景
        if any(word in prompt_lower for word in ["风景", "山", "水", "landscape", "nature", "mountain", "river"]):
            analysis["themes"].append("风景")
            analysis["elements"].append("自然景观")
        
        # 识别建筑
        if any(word in prompt_lower for word in ["建筑", "房子", "城市", "building", "city", "architecture"]):
            analysis["themes"].append("建筑")
            analysis["elements"].append"建筑物")
        
        # 识别动物
        if any(word in prompt_lower for word in ["动物", "猫", "狗", "animal", "cat", "dog", "bird"]):
            analysis["themes"].append("动物")
            analysis["elements"].append("动物主体")
        
        # 识别氛围
        if any(word in prompt_lower for word in ["平静", "安静", "peaceful", "calm", "serene"]):
            analysis["mood"] = "平静"
        elif any(word in prompt_lower for word in ["活力", "动态", "dynamic", "energetic", "vibrant"]):
            analysis["mood"] = "活力"
        elif any(word in prompt_lower for word in ["神秘", "mysterious", "mystical", "ethereal"]):
            analysis["mood"] = "神秘"
        elif any(word in prompt_lower for word in ["浪漫", "romantic", "dreamy"]):
            analysis["mood"] = "浪漫"
        elif any(word in prompt_lower for word in ["史诗", "epic", "grand", "majestic"]):
            analysis["mood"] = "史诗"
        
        # 识别风格
        if any(word in prompt_lower for word in ["anime", "动漫", "卡通"]):
            analysis["style"] = "动漫"
        elif any(word in prompt_lower for word in ["cyberpunk", "赛博朋克", "科幻"]):
            analysis["style"] = "赛博朋克"
        elif any(word in prompt_lower for word in ["fantasy", "奇幻", "魔法"]):
            analysis["style"] = "奇幻"
        elif any(word in prompt_lower for word in ["realistic", "写实", "照片"]):
            analysis["style"] = "写实"
        elif any(word in prompt_lower for word in ["oil", "painting", "油画", "水彩"]):
            analysis["style"] = "油画"
        
        return analysis
    
    def enrich_prompt(self, base_prompt: str, analysis: Dict = None) -> str:
        """丰富提示词内容"""
        if not analysis:
            analysis = self.analyze_prompt(base_prompt)
        
        enriched_parts = [base_prompt]
        
        # 添加细节描述
        for theme in analysis["themes"]:
            if theme in self.detail_library:
                details = random.sample(self.detail_library[theme], min(3, len(self.detail_library[theme])))
                enriched_parts.append(", ".join(details))
        
        # 添加艺术风格
        if analysis["style"] in self.art_styles:
            enriched_parts.append(self.art_styles[analysis["style"]])
        
        # 添加灯光效果
        enriched_parts.append(random.choice(self.lighting_effects))
        
        # 添加构图技巧
        enriched_parts.append(random.choice(self.composition_techniques))
        
        # 添加质量增强词
        enriched_parts.append(random.choice(self.quality_enhancers))
        
        # 添加氛围词
        if analysis["mood"] in self.atmosphere_words:
            enriched_parts.append(self.atmosphere_words[analysis["mood"]])
        
        return ", ".join(enriched_parts)
    
    def generate_variants(self, base_prompt: str, count: int = 5) -> List[Dict]:
        """生成多个优化变体"""
        variants = []
        analysis = self.analyze_prompt(base_prompt)
        
        for i in range(count):
            # 每次使用不同的组合
            enriched = self.enrich_prompt(base_prompt, analysis)
            
            variant = {
                "variant_id": i + 1,
                "base_prompt": base_prompt,
                "optimized_prompt": enriched,
                "analysis": {
                    "themes": analysis["themes"],
                    "style": analysis["style"],
                    "mood": analysis["mood"]
                },
                "enhancements": {
                    "details_added": True,
                    "style_applied": analysis["style"],
                    "lighting": "random",
                    "composition": "random",
                    "quality_boost": True
                }
            }
            variants.append(variant)
        
        return variants
    
    def optimize_for_news(self, news_topics: List[Dict], count: int = 5) -> List[Dict]:
        """为新闻主题优化提示词"""
        variants = []
        
        for i in range(count):
            news = news_topics[i % len(news_topics)]
            base = news.get("prompt", news.get("topic", ""))
            
            # 新闻类提示词特殊处理
            enriched_parts = [
                base,
                "news illustration style, professional quality",
                "editorial photography, journalistic approach",
                random.choice(self.lighting_effects),
                random.choice(self.composition_techniques),
                random.choice(self.quality_enhancers)
            ]
            
            variant = {
                "variant_id": i + 1,
                "news_topic": news.get("topic", "custom"),
                "base_prompt": base,
                "optimized_prompt": ", ".join(enriched_parts),
                "analysis": {
                    "themes": ["新闻"],
                    "style": "新闻插画",
                    "mood": "专业"
                },
                "enhancements": {
                    "news_based": True,
                    "professional_style": True,
                    "editorial_quality": True
                }
            }
            variants.append(variant)
        
        return variants
    
    def optimize_for_search(self, search_query: str, count: int = 5) -> List[Dict]:
        """为搜索关键词优化提示词"""
        variants = []
        
        # 基于搜索词扩展场景
        scene_extensions = [
            "daytime scene, clear visibility",
            "night scene, atmospheric lighting",
            "sunset scene, warm colors",
            "morning light, fresh atmosphere",
            "evening atmosphere, golden tones"
        ]
        
        for i in range(count):
            enriched_parts = [
                search_query,
                scene_extensions[i % len(scene_extensions)],
                random.choice(self.lighting_effects),
                random.choice(self.composition_techniques),
                random.choice(self.quality_enhancers)
            ]
            
            # 根据搜索词添加风格
            if "赛博朋克" in search_query or "cyberpunk" in search_query.lower():
                enriched_parts.append(self.art_styles["赛博朋克"])
            elif "奇幻" in search_query or "fantasy" in search_query.lower():
                enriched_parts.append(self.art_styles["奇幻"])
            elif "动漫" in search_query or "anime" in search_query.lower():
                enriched_parts.append(self.art_styles["动漫"])
            
            variant = {
                "variant_id": i + 1,
                "search_query": search_query,
                "base_prompt": search_query,
                "optimized_prompt": ", ".join(enriched_parts),
                "scene": scene_extensions[i % len(scene_extensions)],
                "analysis": self.analyze_prompt(search_query),
                "enhancements": {
                    "search_based": True,
                    "scene_varied": True,
                    "style_matched": True
                }
            }
            variants.append(variant)
        
        return variants
    
    def get_optimization_report(self, variant: Dict) -> str:
        """生成优化报告"""
        report = []
        report.append(f"🎨 变体 #{variant['variant_id']}")
        report.append(f"📝 基础提示词：{variant['base_prompt'][:50]}...")
        report.append(f"✨ 优化后：{variant['optimized_prompt'][:100]}...")
        report.append(f"🎭 主题：{', '.join(variant['analysis'].get('themes', ['未识别']))}")
        report.append(f"🎨 风格：{variant['analysis'].get('style', '默认')}")
        report.append(f"💡 氛围：{variant['analysis'].get('mood', '中性')}")
        
        enhancements = variant.get('enhancements', {})
        if enhancements.get('details_added'):
            report.append("✅ 已添加细节描述")
        if enhancements.get('quality_boost'):
            report.append("✅ 已增强质量")
        if enhancements.get('news_based'):
            report.append("✅ 基于新闻主题")
        if enhancements.get('search_based'):
            report.append("✅ 基于搜索关键词")
        
        return "\n".join(report)


# 测试
if __name__ == "__main__":
    optimizer = LittleBugOptimizer()
    
    # 测试基础优化
    base = "美丽的女孩"
    print(f"\n基础提示词：{base}\n")
    
    variants = optimizer.generate_variants(base, 3)
    for v in variants:
        print(optimizer.get_optimization_report(v))
        print("-" * 60)
