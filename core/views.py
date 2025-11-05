# views.py
import requests
import re
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from urllib.parse import urlparse, unquote
import logging

# Logger oluştur
logger = logging.getLogger(__name__)

def index(request):
    """Ana sayfa"""
    return render(request, 'index.html')

@csrf_exempt
def download_video(request):
    """Pinterest videosunu indir"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            pinterest_url = data.get('url', '').strip()
            
            # Pinterest veya pin.it kontrolü
            if not pinterest_url or ('pinterest' not in pinterest_url.lower() and 'pin.it' not in pinterest_url.lower()):
                return JsonResponse({
                    'success': False,
                    'error': 'Geçerli bir Pinterest linki giriniz'
                })
            
            # Headers'ı önce tanımla - Mobil ve Desktop uyumlu
            headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
            
            # pin.it linklerini takip et
            if 'pin.it' in pinterest_url:
                try:
                    # Session kullan - cookie'leri takip et
                    session = requests.Session()
                    session.headers.update(headers)
                    
                    # Redirect'i takip et
                    redirect_response = session.get(
                        pinterest_url, 
                        allow_redirects=True,
                        timeout=20,
                        verify=True
                    )
                    
                    # Final URL'yi al
                    final_url = redirect_response.url
                    
                    # Eğer hala pin.it ise, Location header'ını kontrol et
                    if 'pin.it' in final_url or 'pinterest.com/pin' not in final_url:
                        # Manuel redirect takibi
                        initial_response = session.get(
                            pinterest_url,
                            allow_redirects=False,
                            timeout=10
                        )
                        
                        if 'Location' in initial_response.headers:
                            final_url = initial_response.headers['Location']
                            logger.info(f"Location header'dan alındı: {final_url}")
                        else:
                            # Son çare: pin.it'ten pin ID'sini çıkarmayı dene
                            pin_code = pinterest_url.split('/')[-1].split('?')[0].strip()
                            if pin_code and len(pin_code) > 5:
                                # pin.it sayfasını çek ve içinden pin ID'yi bul
                                page_content = redirect_response.text
                                pin_match = re.search(r'pinterest\.com/pin/(\d+)', page_content)
                                if pin_match:
                                    final_url = f'https://www.pinterest.com/pin/{pin_match.group(1)}/'
                                    logger.info(f"HTML'den pin ID bulundu: {final_url}")
                    
                    pinterest_url = final_url
                    logger.info(f"Redirect edildi: {pinterest_url}")
                    
                except requests.exceptions.SSLError as e:
                    logger.error(f"SSL Hatası: {e}")
                    # SSL hatası varsa verify=False ile dene
                    try:
                        redirect_response = requests.get(
                            pinterest_url, 
                            headers=headers,
                            allow_redirects=True,
                            timeout=20,
                            verify=False
                        )
                        pinterest_url = redirect_response.url
                        logger.info(f"SSL bypass ile redirect edildi: {pinterest_url}")
                    except Exception as e2:
                        logger.error(f"SSL bypass de başarısız: {e2}")
                        return JsonResponse({
                            'success': False,
                            'error': f'pin.it linki çözümlenemedi. Lütfen pinterest.com linkini kullanın.'
                        })
                except Exception as e:
                    logger.error(f"Redirect hatası: {e}")
                    return JsonResponse({
                        'success': False,
                        'error': f'pin.it linki çözümlenemedi. Lütfen linki tarayıcıda açıp pinterest.com linkini kullanın.'
                    })
            
            # Pinterest sayfasını çek
            
            # Timeout ekle ve redirectleri takip et
            try:
                response = requests.get(
                    pinterest_url, 
                    headers=headers, 
                    allow_redirects=True,
                    timeout=15,
                    verify=True
                )
            except requests.exceptions.ProxyError:
                return JsonResponse({
                    'success': False,
                    'error': 'PythonAnywhere ücretsiz hesabında Pinterest\'e erişim kısıtlı. Lütfen ücretli hesaba geçin veya başka bir hosting kullanın.'
                })
            except requests.exceptions.SSLError:
                # SSL hatası varsa verify=False ile dene
                response = requests.get(
                    pinterest_url, 
                    headers=headers, 
                    allow_redirects=True,
                    timeout=15,
                    verify=False
                )
            
            if response.status_code != 200:
                return JsonResponse({
                    'success': False,
                    'error': f'Pinterest sayfası yüklenemedi (HTTP {response.status_code})'
                })
            
            html_content = response.text
            
            # Debug için
            logger.info(f"Final URL: {response.url}")
            logger.info(f"Status Code: {response.status_code}")
            
            # Video URL'sini bul
            video_url = None
            
            # Method 1: JSON-LD yapısından video URL'sini çek
            json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
            json_matches = re.findall(json_ld_pattern, html_content, re.DOTALL)
            
            for json_str in json_matches:
                try:
                    json_data = json.loads(json_str)
                    if isinstance(json_data, dict) and 'contentUrl' in json_data:
                        video_url = json_data['contentUrl']
                        break
                    elif isinstance(json_data, dict) and 'video' in json_data:
                        if isinstance(json_data['video'], dict):
                            video_url = json_data['video'].get('contentUrl')
                            if video_url:
                                break
                except:
                    continue
            
            # Method 2: __PWS_DATA__ içinden video bilgisini çek
            if not video_url:
                pws_pattern = r'__PWS_DATA__\s*=\s*({.*?});'
                pws_match = re.search(pws_pattern, html_content, re.DOTALL)
                if pws_match:
                    try:
                        pws_data = json.loads(pws_match.group(1))
                        # PWS data içinde video URL'sini ara
                        video_url = find_video_in_dict(pws_data)
                    except:
                        pass
            
            # Method 3: Direkt video URL pattern'lerini ara (GENİŞLETİLMİŞ)
            if not video_url:
                video_patterns = [
                    # V1 video URL'leri
                    r'"contentUrl"\s*:\s*"(https://v1\.pinimg\.com/videos/[^"]+\.mp4[^"]*)"',
                    r'"url"\s*:\s*"(https://v1\.pinimg\.com/videos/[^"]+\.mp4)"',
                    r'(https://v1\.pinimg\.com/videos/[^"]+\.mp4)',
                    
                    # V2 video URL'leri
                    r'"contentUrl"\s*:\s*"(https://v2\.pinimg\.com/videos/[^"]+\.mp4[^"]*)"',
                    r'"url"\s*:\s*"(https://v2\.pinimg\.com/videos/[^"]+\.mp4)"',
                    r'(https://v2\.pinimg\.com/videos/[^"]+\.mp4)',
                    
                    # Genel pinimg video pattern'leri
                    r'"contentUrl"\s*:\s*"(https://[^"]*pinimg\.com/videos/[^"]+\.mp4[^"]*)"',
                    r'"url"\s*:\s*"(https://v\d*\.pinimg\.com/videos/[^"]+\.mp4)"',
                    r'(https://v\d*\.pinimg\.com/videos/[^"]+\.mp4)',
                    r'"video_url"\s*:\s*"(https://[^"]+\.mp4[^"]*)"',
                    r'src="(https://v\d*\.pinimg\.com/videos/[^"]+\.mp4)"',
                    
                    # videos_720p veya diğer kalite seçenekleri
                    r'"url_720p"\s*:\s*"(https://[^"]+\.mp4[^"]*)"',
                    r'"url_hls"\s*:\s*"(https://[^"]+\.m3u8[^"]*)"',
                    
                    # Herhangi bir .mp4 dosyası
                    r'(https://[^"\s]+\.mp4)',
                ]
                
                for pattern in video_patterns:
                    matches = re.findall(pattern, html_content)
                    if matches:
                        video_url = matches[0]
                        logger.info(f"Video bulundu (Pattern): {video_url}")
                        break
            
            if not video_url:
                # Debug: HTML'in bir kısmını logla
                logger.warning("HTML içeriği (ilk 2000 karakter):")
                logger.warning(html_content[:2000])
                logger.warning("\n=== VIDEO ARANIMI ===")
                
                # .mp4 varlığını kontrol et
                if '.mp4' in html_content:
                    logger.info("HTML'de .mp4 bulundu!")
                    # Tüm .mp4 linklerini bul
                    all_mp4s = re.findall(r'(https://[^\s"<>]+\.mp4[^\s"<>]*)', html_content)
                    logger.info(f"Bulunan tüm .mp4 linkleri: {all_mp4s[:5]}")  # İlk 5'ini göster
                else:
                    logger.warning("HTML'de .mp4 bulunamadı - Bu link bir resim olabilir")
                
                return JsonResponse({
                    'success': False,
                    'error': 'Video bulunamadı. Link bir video içermiyor olabilir veya Pinterest yapısı değişmiş olabilir.'
                })
            
            # URL'deki escape karakterlerini temizle
            video_url = video_url.replace('\\u002F', '/').replace('\\/', '/')
            video_url = unquote(video_url)
            
            # Video URL'sinin geçerli olup olmadığını kontrol et
            if not video_url.startswith('http'):
                return JsonResponse({
                    'success': False,
                    'error': 'Geçersiz video URL\'si bulundu'
                })
            
            return JsonResponse({
                'success': True,
                'video_url': video_url
            })
            
        except requests.exceptions.Timeout:
            return JsonResponse({
                'success': False,
                'error': 'İstek zaman aşımına uğradı. Lütfen tekrar deneyin.'
            })
        except requests.exceptions.ConnectionError:
            return JsonResponse({
                'success': False,
                'error': 'Bağlantı hatası. İnternet bağlantınızı kontrol edin.'
            })
        except requests.exceptions.RequestException as e:
            return JsonResponse({
                'success': False,
                'error': f'İstek hatası: {str(e)}'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Beklenmeyen bir hata oluştu: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Geçersiz istek'
    })


def find_video_in_dict(data, depth=0, max_depth=10):
    """Nested dictionary içinde video URL'sini bul"""
    if depth > max_depth:
        return None
    
    if isinstance(data, dict):
        # Video URL anahtarlarını kontrol et
        for key in ['contentUrl', 'video_url', 'url', 'src']:
            if key in data:
                value = data[key]
                if isinstance(value, str) and '.mp4' in value and value.startswith('http'):
                    return value
        
        # Recursive olarak tüm değerleri kontrol et
        for value in data.values():
            result = find_video_in_dict(value, depth + 1, max_depth)
            if result:
                return result
    
    elif isinstance(data, list):
        for item in data:
            result = find_video_in_dict(item, depth + 1, max_depth)
            if result:
                return result
    
    return None