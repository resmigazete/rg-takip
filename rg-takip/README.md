# Resmi Gazete Sağlık Takip (ücretsiz kurulum: GitHub Actions + Pages)

Her gece 00:05'te (Türkiye saati) günün Resmi Gazete sayısını toplar; sağlık düzenlemelerini,
mevzuat değişikliklerini ve önemli atamaları (vali, rektör, sağlık kurumu yöneticileri) ayıklar;
telefonda uygulama gibi açılan bir siteyi günceller.

## Kurulum (yaklaşık 10 dakika, bilgisayarda yapın)
1. github.com'da ücretsiz hesap açın → **New repository** → adı `rg-takip`, **Public** → Create.
2. Bu zip'i açın. İçindeki **tüm dosya ve klasörleri** (`.github` klasörü dahil) depoya yükleyin:
   **Add file → Upload files**. Windows/Mac `.github` klasörünü gizleyebilir; görünmüyorsa
   "gizli dosyaları göster" açın. Yüklenmezse: **Add file → Create new file**, adına
   `.github/workflows/daily.yml` yazıp bu zip'teki aynı dosyanın içeriğini yapıştırın.
3. **Settings → Pages → Build and deployment**: Source = *Deploy from a branch*,
   Branch = `main`, klasör = `/docs` → Save. (docs klasörü ilk çalışmadan sonra oluşur.)
4. (İsteğe bağlı Telegram) **Settings → Secrets and variables → Actions → New repository secret**:
   `TELEGRAM_TOKEN` ve `TELEGRAM_CHAT_ID`.
5. **Actions** sekmesi → *Günlük Resmi Gazete takibi* → **Run workflow**. İlk çalıştırma birkaç
   dakika sürer; yeşil tik çıkınca bitmiştir.
6. Telefonda `https://KULLANICIADINIZ.github.io/rg-takip/` adresini açın →
   iPhone: Safari → Paylaş → *Ana Ekrana Ekle*; Android: Chrome → ⋮ → *Uygulamayı yükle*.

Bundan sonra her gece kendiliğinden çalışır. GitHub zamanlanmış görevleri bazen 5–30 dk gecikir.

## Yerelde deneme
    pip install -r requirements.txt
    python -m pytest -q
    python main.py run --no-wait --no-send
    python -m rgtakip.export          # docs/ üretir

## Önemli: canlıda ilk doğrulama
`parser.py` ve `fetcher.py` Resmi Gazete'nin arşiv URL kalıbına göre yazıldı
(/eskiler/YYYY/MM/YYYYMMDD.htm). İlk gerçek çalıştırmada fihrist yapısını kontrol edin;
değişiklik gerekirse yalnızca `parser.py` etkilenir. Testlerdeki örnekler uydurmadır.
GitHub'ın sunucularından siteye erişim de ilk çalıştırmada denenmelidir.

## Diğer çalışma biçimleri
- Kendi sunucunuzda: `RG_API_TOKEN=... ./start.sh` (Dockerfile ve render.yaml dahil)

## Yol haritası
1. mevzuat.gov.tr'den eski madde metnini çekip gerçek diff üret
2. LLM katmanı: belirsiz kayıtlar için doğrulama + kaynaklı özet
3. Atama zinciri ve mevzuat ilişki grafiği
4. Takip listeleri ve kişisel uyarılar
