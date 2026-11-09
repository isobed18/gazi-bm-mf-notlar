# Katkı rehberi / Contributing

Dosyalar git'te değil, bakımcıların Google Drive aynasında tutulur. **Dosya göndermenin ana yolu "Gazi BM Kaynak Gönder"
Google Formu**: https://docs.google.com/forms/d/e/1FAIpQLSccuOWOSr4S9dCxMROm2lOoa0IgOjIznh9X3YZ1ieTljdW9Ng/viewform: dosyaları yükle, dersi ve türü yaz, gönder. GitHub hesabı gerekmez; gönderdiğin dosyaları
başkası göremez ya da silemez. Haftalık bakımda bir agent dosyaları tarar (virüs, tür, gizlilik), doğru derse yerleştirir,
emin olamadığını bir insana sorar. Ayrıntılar: [docs/SUBMISSIONS.md](docs/SUBMISSIONS.md).

## Kısa yol: agent ile (önerilen)
1. Dosyaları bir klasöre koy ve kendi agent'ını (Claude, ChatGPT, Gemini, Codex…) aç.
2. "Bu dosyaları Gazi BM arşivine gönder, yönerge: https://github.com/isobed18/gazi-bm-mf-notlar/blob/main/.agents/skills/contributor-submit/SKILL.md"
   de. Agent dosyaları okur, kişisel veri olanları ayıklar, **ders + tür** gruplarına ayırır ve her grup için formda ne
   seçileceğini tablo halinde verir; tarayıcı kontrolü varsa formu kendisi doldurur. Her gönderim tek ders + tek tür.

## Elle
Formu aç, dosyaları yükle (en fazla 10, zip/rar değil), dersi ve türü seç, yıl/dönemi yaz, gönder. Başka ders veya tür
için "Başka bir yanıt gönder". GitHub kullananlar "Kaynak önerisi" issue'su da açabilir.

## Pull request ne zaman?
Sadece metin değişiklikleri için: metadata düzeltmesi, kataloğa yeni bir seçmeli ders eklemek, doküman.
PR'a dosya (pdf, resim…) eklenirse CI reddeder.

## Kurallar
- Kişisel veri yok: sohbet ekran görüntüleri, telefon numarası, kimlik ve kişisel fotoğraflar yasak.
  Sınav ve ödev kağıtlarındaki isimler sorun değil.
- Telifli kitapların tamamını yükleme, link ver.
- Çalıştırılabilir dosyalar ve makrolu Office dosyaları (`.docm`, `.xlsm`) kabul edilmez. `.rar` ve `.7z` dosyalarını önce aç.
- Kendi notların `student-notes` türüne girer (isteğe bağlı katman; isteyen indirmez).
