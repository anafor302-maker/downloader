# views.py
import requests
import re
from django.shortcuts import render, redirect
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from urllib.parse import unquote
import logging

# Logger oluştur
logger = logging.getLogger(__name__)

def get_user_language_from_ip(request):
    """Kullanıcının IP adresinden dilini tespit et"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    try:
        response = requests.get(f'https://ipapi.co/{ip}/json/', timeout=2)
        data = response.json()
        country_code = data.get('country_code', '').upper()
        
        # Ülke koduna göre dil belirle
        if country_code == 'TR':
            return 'tr'
        elif country_code in ['SA', 'AE', 'EG', 'IQ', 'JO', 'KW', 'LB', 'LY', 'MA', 'OM', 'PS', 'QA', 'SD', 'SY', 'TN', 'YE', 'BH', 'DZ']:
            return 'ar'
        else:
            return 'en'
    except:
        # Hata durumunda tarayıcı dilini kontrol et
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        if 'tr' in accept_language.lower():
            return 'tr'
        elif 'ar' in accept_language.lower():
            return 'ar'
        return 'en'

def index(request):
    """Ana sayfa - Türkçe"""
    # İlk ziyarette yönlendirme yap
    if not request.session.get('language_detected'):
        detected_lang = get_user_language_from_ip(request)
        request.session['language_detected'] = True
        
        if detected_lang == 'en':
            return redirect('/en/')
        elif detected_lang == 'ar':
            return redirect('/ar/')
    
    return render(request, 'index_tr.html')

def index_en(request):
    """İngilizce sayfa"""
    return render(request, 'index_en.html')

def index_ar(request):
    """Arapça sayfa"""
    return render(request, 'index_ar.html')


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

            # Pin ID'yi çıkar (dosya adı için)
            pin_id = 'video'
            pin_match = re.search(r'/pin/(\d+)', pinterest_url)
            if pin_match:
                pin_id = pin_match.group(1)

            return JsonResponse({
                'success': True,
                'video_url': video_url,
                'pin_id': pin_id
            })

        except requests.exceptions.Timeout:
            return JsonResponse({'success': False, 'error': 'İstek zaman aşımına uğradı.'})
        except requests.exceptions.ConnectionError:
            return JsonResponse({'success': False, 'error': 'Bağlantı hatası. Lütfen tekrar deneyin.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Beklenmeyen hata: {str(e)}'})

    return JsonResponse({'success': False, 'error': 'Geçersiz istek'})


@require_http_methods(["GET"])
def proxy_download(request):
    """Videoyu proxy üzerinden indir ve kullanıcıya sun"""
    try:
        video_url = request.GET.get('url')
        filename = request.GET.get('filename', 'pinterest-video.mp4')
        
        if not video_url:
            return HttpResponse('Video URL gerekli', status=400)
        
        # Video'yu stream olarak indir
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.pinterest.com/',
            'Accept': '*/*',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
        }
        
        logger.info(f"Video indiriliyor: {video_url}")
        
        # Video'yu indir (stream mode)
        video_response = requests.get(
            video_url, 
            headers=headers, 
            stream=True, 
            timeout=30,
            verify=True
        )
        
        video_response.raise_for_status()
        
        # Content-Type'ı kontrol et
        content_type = video_response.headers.get('Content-Type', 'video/mp4')
        content_length = video_response.headers.get('Content-Length', '')
        
        logger.info(f"Video başarıyla alındı. Content-Type: {content_type}, Size: {content_length}")
        
        # StreamingHttpResponse ile videoyu sun
        response = StreamingHttpResponse(
            video_response.iter_content(chunk_size=8192),
            content_type=content_type
        )
        
        # İndirme için gerekli header'lar - BU ÇOK ÖNEMLİ!
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        if content_length:
            response['Content-Length'] = content_length
        
        response['Accept-Ranges'] = 'bytes'
        response['Cache-Control'] = 'no-cache'
        
        logger.info(f"Video kullanıcıya gönderiliyor: {filename}")
        
        return response
        
    except requests.exceptions.Timeout:
        logger.error("Video indirme zaman aşımı")
        return HttpResponse('Video indirme zaman aşımına uğradı', status=504)
    except requests.exceptions.RequestException as e:
        logger.error(f"Video indirme hatası: {str(e)}")
        return HttpResponse(f'Video indirme hatası: {str(e)}', status=500)
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")
        return HttpResponse(f'Hata: {str(e)}', status=500)


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