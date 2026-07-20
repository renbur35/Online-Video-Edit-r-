import streamlit as st
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
import tempfile
import os
import time
import proglog

def fit_cover(clip, target_w, target_h):
    """Klibi orantısını koruyarak hedef boyutu tam kaplayacak
    şekilde ölçeklendirir ve ortadan kırpar (object-fit: cover)."""
    scale = max(target_w / clip.w, target_h / clip.h)
    clip = clip.resized(scale)
    clip = clip.cropped(
        x_center=clip.w / 2,
        y_center=clip.h / 2,
        width=target_w,
        height=target_h
    )
    return clip

class StreamlitLogger(proglog.ProgressBarLogger):
    def __init__(self, st_bar, st_text):
        super().__init__()
        self.st_bar = st_bar
        self.st_text = st_text

    def bars_callback(self, bar, attr, value, old_value=None):
        total = self.bars[bar].get('total', 0)
        if total > 0:
            perc = int((value / total) * 100)
            perc = max(0, min(100, perc))
            self.st_bar.progress(perc)
            
            if bar == 'chunk':
                self.st_text.markdown(f"**Ses İşleniyor:** `%{perc}` tamamlandı...")
            elif bar == 't':
                self.st_text.markdown(f"**Görüntü İşleniyor:** `%{perc}` tamamlandı...")
            else:
                self.st_text.markdown(f"**İşleniyor:** `%{perc}` tamamlandı...")

# Sayfa ayarları
st.set_page_config(page_title="Video Editörü", page_icon="🎬")

st.markdown("""
<style>
    /* Streamlit varsayılan metinlerini Türkçeleştirme */
    div[data-testid="stFileUploader"] button[data-testid="baseButton-secondary"] {
        color: transparent !important;
    }
    div[data-testid="stFileUploader"] button[data-testid="baseButton-secondary"]::after {
        content: "Yükle";
        color: inherit;
        position: absolute;
        font-size: 14px;
    }
    div[data-testid="stFileUploaderDropzoneInstructions"] > div > span {
        display: none;
    }
    div[data-testid="stFileUploaderDropzoneInstructions"] > div::before {
        content: "Sürükleyip bırakın veya yükleyin";
    }
</style>
""", unsafe_allow_html=True)

st.title("🎬 Video Editörü")
st.markdown("Videonuzun formatını otomatik algılayıp doğru logo ve jeneriği ekler.<br>*Maksimum süre: 2 dakika 55 saniye*", unsafe_allow_html=True)

# Yalnızca video yükleyici
video_file = st.file_uploader("Videonuzu seçin (MP4, MOV)", type=['mp4', 'mov'])

# Logo ve Outro yolları
dik_logo_path = "diklogo.png"
yatay_logo_path = "yataylogo.png"
dik_outro_path = "dikoutro.mp4"
yatay_outro_path = "yatayoutro.mp4"

if video_file:
    if st.button("Videoyu İşle"):
        with st.spinner("Videonuz analiz ediliyor ve işleniyor, lütfen bekleyin..."):
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
                temp_video.write(video_file.read())
                video_path = temp_video.name

            output_path = "output_video.mp4"

            try:
                # Videoyu yükle
                video = VideoFileClip(video_path)
                
                # Süre kontrolü
                if video.duration > 175:
                    st.error("Hata: Videonuz 2 dakika 55 saniyeden uzun olamaz!")
                else:
                    # FORMAT ALGILAMA: Yükseklik > Genişlik ise dikey, değilse yatay
                    is_vertical = video.h > video.w
                    
                    if is_vertical:
                        selected_logo_path = dik_logo_path
                        selected_outro_path = dik_outro_path
                        format_text = "Dikey"
                    else:
                        selected_logo_path = yatay_logo_path
                        selected_outro_path = yatay_outro_path
                        format_text = "Yatay"
                        
                    # Seçilen logonun klasörde olup olmadığını kontrol et
                    if not os.path.exists(selected_logo_path):
                        st.error(f"⚠️ Hata: {format_text} video algılandı ancak '{selected_logo_path}' bulunamadı! Lütfen ilgili logoyu uygulamanın bulunduğu klasöre ekleyin.")
                    elif not os.path.exists(selected_outro_path):
                        st.error(f"⚠️ Hata: {format_text} video algılandı ancak '{selected_outro_path}' bulunamadı! Lütfen ilgili jenerik videosunu klasöre ekleyin.")
                    else:
                        st.info(f"📹 {format_text} video algılandı. '{selected_logo_path}' ve '{selected_outro_path}' ekleniyor...")
                        
                        # Logoyu yükle ve önceki versiyondaki gibi video genişliğinin %100'üne ayarla
                        logo = ImageClip(selected_logo_path)
                        logo_width = int(video.w * 1.00)
                        logo = logo.resized(width=logo_width)
                        
                        # Logoyu sol üste sabitle ve süreyi eşitle
                        logo = logo.with_position(("left", "top")).with_duration(video.duration)
                        
                        # Video ve Logoyu birleştir
                        video_with_logo = CompositeVideoClip([video, logo])
                        
                        # Outro'yu yükle ve ana videonun boyutlarına uyarla
                        outro = VideoFileClip(selected_outro_path)
                        outro = fit_cover(outro, video.w, video.h)
                        
                        # Video ile Outro'yu arka arkaya birleştir
                        final_video = concatenate_videoclips([video_with_logo, outro])
                        
                        # Progress bar için alan
                        st_progress_bar = st.progress(0)
                        st_progress_text = st.empty()
                        logger = StreamlitLogger(st_progress_bar, st_progress_text)
                        
                        # Çıktıyı al (Mobil uyumluluk için yuv420p ve crf 23 ayarları eklendi)
                        final_video.write_videofile(
                            output_path, 
                            codec="libx264", 
                            audio_codec="aac", 
                            fps=video.fps,
                            preset="medium",
                            ffmpeg_params=["-pix_fmt", "yuv420p", "-crf", "23"],
                            logger=logger
                        )
                        
                        st_progress_bar.progress(100)
                        st_progress_text.markdown("**✅ İşlem tamamlandı! 🎉**")
                        st.success("İşlem tamamlandı! 🎉")
                        
                        # Önbellek sorununu aşmak için isme zaman damgası ekliyoruz
                        download_filename = f"logolu_video_{int(time.time())}.mp4"
                        
                        with open(output_path, "rb") as file:
                            btn = st.download_button(
                                label="📥 İşlenmiş Videoyu İndir",
                                data=file,
                                file_name=download_filename,
                                mime="video/mp4"
                            )
            except Exception as e:
                st.error(f"Bir hata oluştu: {e}")
            finally:
                # Temizlik
                if 'video' in locals():
                    try:
                        video.close()
                    except:
                        pass
                if 'outro' in locals():
                    try:
                        outro.close()
                    except:
                        pass
                if os.path.exists(video_path): 
                    os.remove(video_path)
