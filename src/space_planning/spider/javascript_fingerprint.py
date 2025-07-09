#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JavaScript指纹伪装模块
"""

import random
import json
import base64
from typing import Dict, List

class JavaScriptFingerprint:
    """JavaScript指纹伪装器"""
    
    def __init__(self):
        # Canvas指纹
        self.canvas_fingerprints = [
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QzwAEhAI/jDDKQAAAAABJRU5ErkJggg=="
        ]
        
        # WebGL指纹
        self.webgl_vendors = [
            "Google Inc. (Intel)",
            "Intel Inc.",
            "NVIDIA Corporation",
            "AMD",
            "Apple Inc."
        ]
        
        self.webgl_renderers = [
            "ANGLE (Intel, Intel(R) HD Graphics 620 Direct3D11 vs_5_0 ps_5_0)",
            "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0)",
            "ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)",
            "Intel(R) HD Graphics 620",
            "NVIDIA GeForce GTX 1060"
        ]
        
        # 音频指纹
        self.audio_contexts = [
            "AudioContext",
            "webkitAudioContext",
            "mozAudioContext"
        ]
        
        # 字体指纹
        self.fonts = [
            "Arial", "Helvetica", "Times New Roman", "Courier New",
            "Verdana", "Georgia", "Palatino", "Garamond", "Bookman",
            "Comic Sans MS", "Trebuchet MS", "Arial Black", "Impact"
        ]
        
        # 插件指纹
        self.plugins = [
            "PDF Viewer",
            "Chrome PDF Plugin",
            "Chromium PDF Plugin",
            "Native Client",
            "Widevine Content Decryption Module"
        ]
        
        # 语言指纹
        self.languages = [
            "zh-CN", "zh-TW", "en-US", "en-GB", "ja-JP", "ko-KR",
            "fr-FR", "de-DE", "es-ES", "it-IT", "pt-BR", "ru-RU"
        ]
    
    def generate_canvas_fingerprint(self) -> str:
        """生成Canvas指纹"""
        return random.choice(self.canvas_fingerprints)
    
    def generate_webgl_fingerprint(self) -> Dict[str, str]:
        """生成WebGL指纹"""
        return {
            'vendor': random.choice(self.webgl_vendors),
            'renderer': random.choice(self.webgl_renderers),
            'version': f"{random.randint(1, 4)}.{random.randint(0, 9)}.{random.randint(0, 9)}"
        }
    
    def generate_audio_fingerprint(self) -> Dict:
        """生成音频指纹"""
        return {
            'context': random.choice(self.audio_contexts),
            'sampleRate': random.choice([44100, 48000, 22050]),
            'channelCount': random.choice([1, 2]),
            'maxChannelCount': random.choice([2, 4, 6])
        }
    
    def generate_font_fingerprint(self) -> List[str]:
        """生成字体指纹"""
        return random.sample(self.fonts, random.randint(5, 10))
    
    def generate_plugin_fingerprint(self) -> List[str]:
        """生成插件指纹"""
        return random.sample(self.plugins, random.randint(2, 5))
    
    def generate_language_fingerprint(self) -> List[str]:
        """生成语言指纹"""
        return random.sample(self.languages, random.randint(1, 3))
    
    def generate_screen_fingerprint(self) -> Dict:
        """生成屏幕指纹"""
        resolutions = [
            (1920, 1080), (1366, 768), (1440, 900), (2560, 1440),
            (1600, 900), (1280, 720), (3840, 2160), (2560, 1600)
        ]
        
        width, height = random.choice(resolutions)
        return {
            'width': width,
            'height': height,
            'availWidth': width,
            'availHeight': height,
            'colorDepth': random.choice([24, 32]),
            'pixelDepth': random.choice([24, 32])
        }
    
    def generate_timezone_fingerprint(self) -> Dict:
        """生成时区指纹"""
        timezones = [
            'Asia/Shanghai', 'Asia/Beijing', 'Asia/Hong_Kong',
            'America/New_York', 'America/Los_Angeles', 'Europe/London',
            'Europe/Paris', 'Europe/Berlin', 'Asia/Tokyo', 'Asia/Seoul'
        ]
        
        return {
            'timezone': random.choice(timezones),
            'offset': random.randint(-12, 12) * 60,
            'dst': random.choice([True, False])
        }
    
    def generate_complete_fingerprint(self) -> Dict:
        """生成完整的JavaScript指纹"""
        return {
            'canvas': self.generate_canvas_fingerprint(),
            'webgl': self.generate_webgl_fingerprint(),
            'audio': self.generate_audio_fingerprint(),
            'fonts': self.generate_font_fingerprint(),
            'plugins': self.generate_plugin_fingerprint(),
            'languages': self.generate_language_fingerprint(),
            'screen': self.generate_screen_fingerprint(),
            'timezone': self.generate_timezone_fingerprint(),
            'navigator': {
                'userAgent': self._generate_user_agent(),
                'platform': random.choice(['Win32', 'MacIntel', 'Linux x86_64']),
                'language': random.choice(self.languages),
                'languages': self.generate_language_fingerprint(),
                'cookieEnabled': True,
                'doNotTrack': random.choice([None, '1', '0']),
                'onLine': True,
                'hardwareConcurrency': random.choice([2, 4, 8, 16]),
                'maxTouchPoints': random.choice([0, 1, 5, 10])
            }
        }
    
    def _generate_user_agent(self) -> str:
        """生成User-Agent"""
        browsers = [
            {
                'name': 'Chrome',
                'versions': ['120.0.0.0', '119.0.0.0', '118.0.0.0'],
                'platforms': ['Windows NT 10.0; Win64; x64', 'Macintosh; Intel Mac OS X 10_15_7']
            },
            {
                'name': 'Firefox',
                'versions': ['120.0', '119.0', '118.0'],
                'platforms': ['Windows NT 10.0; Win64; x64', 'Macintosh; Intel Mac OS X 10.15; rv:120.0']
            },
            {
                'name': 'Safari',
                'versions': ['605.1.15', '604.1.38', '603.3.8'],
                'platforms': ['Macintosh; Intel Mac OS X 10_15_7']
            }
        ]
        
        browser = random.choice(browsers)
        version = random.choice(browser['versions'])
        platform = random.choice(browser['platforms'])
        
        return f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) {browser['name']}/{version} Safari/537.36"
    
    def generate_js_code(self) -> str:
        """生成JavaScript代码来设置指纹"""
        fingerprint = self.generate_complete_fingerprint()
        
        js_code = f"""
        // JavaScript指纹伪装
        (function() {{
            // Canvas指纹
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            ctx.fillText('Fingerprint', 10, 10);
            
            // 重写Canvas方法
            const originalToDataURL = canvas.toDataURL;
            canvas.toDataURL = function() {{
                return '{fingerprint['canvas']}';
            }};
            
            // WebGL指纹
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) {{
                    return '{fingerprint['webgl']['vendor']}';
                }}
                if (parameter === 37446) {{
                    return '{fingerprint['webgl']['renderer']}';
                }}
                return getParameter.call(this, parameter);
            }};
            
            // 屏幕指纹
            Object.defineProperty(screen, 'width', {{
                get: function() {{ return {fingerprint['screen']['width']}; }}
            }});
            Object.defineProperty(screen, 'height', {{
                get: function() {{ return {fingerprint['screen']['height']}; }}
            }});
            Object.defineProperty(screen, 'colorDepth', {{
                get: function() {{ return {fingerprint['screen']['colorDepth']}; }}
            }});
            
            // 时区指纹
            Object.defineProperty(Intl, 'DateTimeFormat', {{
                get: function() {{
                    return function(locale, options) {{
                        return {{
                            resolvedOptions: function() {{
                                return {{
                                    timeZone: '{fingerprint['timezone']['timezone']}'
                                }};
                            }}
                        }};
                    }};
                }}
            }});
            
            // 字体指纹
            const originalQuerySelector = document.querySelector;
            document.querySelector = function(selector) {{
                if (selector === 'body') {{
                    return {{
                        style: {{
                            fontFamily: '{", ".join(fingerprint["fonts"][:3])}'
                        }}
                    }};
                }}
                return originalQuerySelector.call(this, selector);
            }};
            
            // 插件指纹
            Object.defineProperty(navigator, 'plugins', {{
                get: function() {{
                    return {{
                        length: {len(fingerprint['plugins'])},
                        item: function(index) {{
                            return {{
                                name: '{fingerprint["plugins"][0] if fingerprint["plugins"] else ""}',
                                description: 'Plugin Description',
                                filename: 'plugin.dll'
                            }};
                        }}
                    }};
                }}
            }});
            
            // 语言指纹
            Object.defineProperty(navigator, 'language', {{
                get: function() {{ return '{fingerprint["languages"][0] if fingerprint["languages"] else "en-US"}'; }}
            }});
            
            Object.defineProperty(navigator, 'languages', {{
                get: function() {{ return {json.dumps(fingerprint['languages'])}; }}
            }});
            
            // User-Agent
            Object.defineProperty(navigator, 'userAgent', {{
                get: function() {{ return '{fingerprint['navigator']['userAgent']}'; }}
            }});
            
            // 硬件并发数
            Object.defineProperty(navigator, 'hardwareConcurrency', {{
                get: function() {{ return {fingerprint['navigator']['hardwareConcurrency']}; }}
            }});
            
            console.log('JavaScript指纹伪装已启用');
        }})();
        """
        
        return js_code
    
    def encode_fingerprint(self, fingerprint: Dict) -> str:
        """编码指纹为Base64"""
        fingerprint_str = json.dumps(fingerprint, sort_keys=True)
        return base64.b64encode(fingerprint_str.encode()).decode()

# 全局实例
js_fingerprint = JavaScriptFingerprint() 