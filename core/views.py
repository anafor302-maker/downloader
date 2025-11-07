# views.py
import requests
import re
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from urllib.parse import unquote
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
            
            # Geçerli URL kontrolü
            if not pinterest_url or ('pinterest' not in pinterest_url.lower() and 'pin.it' not in pinterest_url.lower()):
                return JsonResponse({
                    'success': False,
                    'error': 'Geçerli bir Pinterest linki giriniz'
                })
            
            # pin.it çözümleme (redirect takip ederek gerçek Pinterest URL'sine ulaş)
            if 'pin.it' in pinterest_url:
                try:
                    r = requests.head(pinterest_url, allow_redirects=True, timeout=10)
                    final_url = r.url
                    if 'pinterest.com' in final_url:
                        pinterest_url = final_url
                        logger.info(f"pin.it yönlendirildi: {final_url}")
                    else:
                        return JsonResponse({
                            'success': False,
                            'error': 'pin.it yönlendirmesi Pinterest sayfasına ulaşamadı.'
                        })
                except Exception as e:
                    return JsonResponse({
                        'success': False,
                        'error': f'pin.it linki çözümlenirken hata oluştu: {str(e)}'
                    })
            
            # Request headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }

            # Pinterest sayfasını çek
            try:
                response = requests.get(
                    pinterest_url,
                    headers=headers,
                    allow_redirects=True,
                    timeout=15,
                    verify=True
                )
            except requests.exceptions.SSLError:
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
            video_url = None

            # 1️⃣ JSON-LD içinden video URL'si
            json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
            json_matches = re.findall(json_ld_pattern, html_content, re.DOTALL)

            for json_str in json_matches:
                try:
                    json_data = json.loads(json_str)
                    if isinstance(json_data, dict):
                        if 'contentUrl' in json_data:
                            video_url = json_data['contentUrl']
                            break
                        elif 'video' in json_data and isinstance(json_data['video'], dict):
                            video_url = json_data['video'].get('contentUrl')
                            if video_url:
                                break
                except:
                    continue

            # 2️⃣ __PWS_DATA__ içinden
            if not video_url:
                pws_pattern = r'__PWS_DATA__\s*=\s*({.*?});'
                pws_match = re.search(pws_pattern, html_content, re.DOTALL)
                if pws_match:
                    try:
                        pws_data = json.loads(pws_match.group(1))
                        video_url = find_video_in_dict(pws_data)
                    except:
                        pass

            # 3️⃣ Fallback: mp4 pattern arama
            if not video_url:
                video_patterns = [
                    r'(https://v\d*\.pinimg\.com/videos/[^"]+\.mp4)',
                    r'"contentUrl"\s*:\s*"(https://[^"]+\.mp4[^"]*)"',
                    r'"url"\s*:\s*"(https://[^"]+\.mp4)"',
                    r'src="(https://[^"]+\.mp4)"',
                ]
                for pattern in video_patterns:
                    matches = re.findall(pattern, html_content)
                    if matches:
                        video_url = matches[0]
                        break

            if not video_url:
                return JsonResponse({
                    'success': False,
                    'error': 'Video bulunamadı. Link bir video içermiyor olabilir.'
                })

            # Temizle
            video_url = video_url.replace('\\u002F', '/').replace('\\/', '/')
            video_url = unquote(video_url)

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
            return JsonResponse({'success': False, 'error': 'İstek zaman aşımına uğradı.'})
        except requests.exceptions.ConnectionError:
            return JsonResponse({'success': False, 'error': 'Bağlantı hatası. Lütfen tekrar deneyin.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Beklenmeyen hata: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Geçersiz istek'})


def find_video_in_dict(data, depth=0, max_depth=10):
    """Nested dict içinde video URL'sini bul"""
    if depth > max_depth:
        return None

    if isinstance(data, dict):
        for key in ['contentUrl', 'video_url', 'url', 'src']:
            val = data.get(key)
            if isinstance(val, str) and '.mp4' in val and val.startswith('http'):
                return val
        for val in data.values():
            found = find_video_in_dict(val, depth + 1, max_depth)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_video_in_dict(item, depth + 1, max_depth)
            if found:
                return found

    return None
