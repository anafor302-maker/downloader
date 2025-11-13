// CSRF Token için
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

// FAQ Accordion
function initFAQ() {
    const faqQuestions = document.querySelectorAll('.faq-question');
    
    faqQuestions.forEach(question => {
        question.addEventListener('click', function() {
            const faqItem = this.parentElement;
            const isActive = faqItem.classList.contains('active');
            
            document.querySelectorAll('.faq-item').forEach(item => {
                item.classList.remove('active');
            });
            
            if (!isActive) {
                faqItem.classList.add('active');
            }
        });
    });
}

// Show/hide messages
function showMessage(id) {
    document.querySelectorAll('.status-message').forEach(msg => {
        msg.classList.remove('show');
    });
    document.getElementById(id).classList.add('show');
}

function setErrorMessage(message) {
    document.getElementById('error-message').textContent = '✗ ' + message;
    showMessage('error-message');
}

function setInfoMessage(message) {
    document.getElementById('info-message').textContent = 'ℹ ' + message;
    showMessage('info-message');
}

// Search Button Handler - BACKEND BAĞLANTISI
document.getElementById('search-btn').addEventListener('click', async function() {
    const urlInput = document.getElementById('pinterest-url');
    const url = urlInput.value.trim();
    const btn = this;
    
    // Mesajları temizle
    document.querySelectorAll('.status-message').forEach(msg => {
        msg.classList.remove('show');
    });
    document.getElementById('video-result').classList.remove('show');
    
    // Validation
    if (!url) {
        setErrorMessage('Lütfen bir Pinterest linki girin!');
        return;
    }
    
    if (!url.includes('pinterest') && !url.includes('pin.it')) {
        setErrorMessage('Lütfen geçerli bir Pinterest linki girin!');
        return;
    }
    
    // Loading başlat
    btn.disabled = true;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<div class="spinner" style="display: inline-block; width: 20px; height: 20px; margin-right: 10px; border-width: 2px;"></div> İşleniyor...';
    showMessage('loading-message');
    
    try {
        // Backend'e istek gönder
        const response = await fetch('/download/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({ 
                url: url,
                is_mobile: /Mobile|Android|iPhone/i.test(navigator.userAgent)
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Video bulundu
            showMessage('success-message');
            
            // Video URL'sini set et
            const videoSource = document.getElementById('video-source');
            const videoPreview = document.getElementById('video-preview');
            const downloadBtn = document.getElementById('download-btn');
            
            // Preview için orjinal URL
            videoSource.src = data.video_url;
            videoPreview.load();
            
            // İndirme için proxy URL kullan - BU ÇOK ÖNEMLİ!
            const downloadUrl = `/proxy-download/?url=${encodeURIComponent(data.video_url)}&filename=pinterest-${data.pin_id}.mp4`;
            downloadBtn.href = downloadUrl;
            downloadBtn.setAttribute('data-video-url', data.video_url);
            downloadBtn.setAttribute('data-pin-id', data.pin_id);
            
            // Video sonuç alanını göster
            document.getElementById('video-result').classList.add('show');
            
            // Scroll to video
            setTimeout(() => {
                document.getElementById('video-result').scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'center' 
                });
            }, 300);
            
            // Başarı mesajını 3 saniye sonra gizle
            setTimeout(() => {
                document.getElementById('success-message').classList.remove('show');
            }, 3000);
        } else {
            // Hata
            setErrorMessage(data.error || 'Video bulunamadı. Lütfen geçerli bir Pinterest video linki girin.');
        }
    } catch (error) {
        console.error('Error:', error);
        setErrorMessage('Bağlantı hatası oluştu. Lütfen tekrar deneyin.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
});

// Enter key ile arama
document.getElementById('pinterest-url').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        document.getElementById('search-btn').click();
    }
});

// Download Button Handler - DİREKT İNDİRME
document.getElementById('download-btn').addEventListener('click', function(e) {
    // Proxy üzerinden indirme yapılacak
    // href zaten proxy URL'sine ayarlı, tarayıcı otomatik indirecek
    
    // Kullanıcıya bilgi ver
    const notification = document.createElement('div');
    notification.className = 'status-message status-success show';
    notification.textContent = '✓ Video indiriliyor... Lütfen bekleyin.';
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.left = '50%';
    notification.style.transform = 'translateX(-50%)';
    notification.style.zIndex = '1000';
    notification.style.maxWidth = '90%';
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.textContent = '✓ Video indiriliyor! İndirilenler klasörünüzü kontrol edin.';
    }, 2000);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
    
    console.log('Video indirme başlatıldı (proxy üzerinden)');
});

// Sayfa yüklendiğinde
document.addEventListener('DOMContentLoaded', () => {
    initFAQ();
});

// Scroll animation
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '0';
            entry.target.style.transform = 'translateY(20px)';
            setTimeout(() => {
                entry.target.style.transition = 'all 0.6s ease-out';
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }, 100);
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

document.querySelectorAll('.step-card, .testimonial-card, .stat-card').forEach(el => {
    observer.observe(el);
});