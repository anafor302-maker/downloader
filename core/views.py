import requests
import re
from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
import json

def index(request):
    """Ana sayfa"""
    return render(request, 'index.html')

@csrf_exempt
def download_video(request):
    """Pinterest videosunu indir"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            pinterest_url = data.get('url', '')
            
            if not pinterest_url or 'pinterest' not in pinterest_url.lower():
                return JsonResponse({
                    'success': False,
                    'error': 'Geçerli bir Pinterest linki giriniz'
                })
            
            # Pinterest sayfasını çek
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(pinterest_url, headers=headers)
            
            if response.status_code != 200:
                return JsonResponse({
                    'success': False,
                    'error': 'Pinterest sayfası yüklenemedi'
                })
            
            # Video URL'sini bul
            video_url = None
            
            # Method 1: JSON-LD yapısından video URL'sini çek
            json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
            json_matches = re.findall(json_ld_pattern, response.text, re.DOTALL)
            
            for json_str in json_matches:
                try:
                    json_data = json.loads(json_str)
                    if isinstance(json_data, dict) and 'contentUrl' in json_data:
                        video_url = json_data['contentUrl']
                        break
                    elif isinstance(json_data, dict) and 'video' in json_data:
                        if isinstance(json_data['video'], dict):
                            video_url = json_data['video'].get('contentUrl')
                            break
                except:
                    continue
            
            # Method 2: Direkt video URL'sini ara
            if not video_url:
                video_patterns = [
                    r'"contentUrl":"(https://[^"]+\.mp4[^"]*)"',
                    r'"url":"(https://v\d*\.pinimg\.com/videos/[^"]+\.mp4)"',
                    r'(https://v\d*\.pinimg\.com/videos/[^"]+\.mp4)',
                ]
                
                for pattern in video_patterns:
                    matches = re.findall(pattern, response.text)
                    if matches:
                        video_url = matches[0]
                        break
            
            if not video_url:
                return JsonResponse({
                    'success': False,
                    'error': 'Video bulunamadı. Link bir video içermiyor olabilir.'
                })
            
            # URL'deki escape karakterlerini temizle
            video_url = video_url.replace('\\u002F', '/')
            
            return JsonResponse({
                'success': True,
                'video_url': video_url
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Bir hata oluştu: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Geçersiz istek'
    })