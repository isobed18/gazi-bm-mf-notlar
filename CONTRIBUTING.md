# Katkı rehberi / Contributing

Dosyalar git'te değil, bakımcıların Google Drive aynasında tutulur. Bu yüzden **dosya paylaşmanın yolu issue açmaktır**.
Depo agent'ı dosyaları inceler, doğru derse yerleştirir, Drive'a yükler ve metadata için bir PR açar. Bir insan onaylar.

## Kısa yol: agent ile
1. Depoyu klonla ve kendi agent'ını (Claude Code, Codex, Gemini/agy…) depo klasöründe aç.
2. "Şu dosyaları depoya öner: …" de. Agent `AGENTS.md` ve `.agents/skills/contributor-submit` yönergelerine göre
   dosyaları tarar, hangi derse ve türe ait olduklarını belirler ve **"Kaynak önerisi"** issue'sunu dosyalarla birlikte açar.

## Elle
**Issues → New issue → "Kaynak önerisi / Resource submission"** formunu doldur. Dosyaları sürükleyip bırak ya da bir
paylaşım linki ver. Ders, tür ve yıl/dönem bilgisini yaz.

## Pull request ne zaman?
Sadece metin değişiklikleri için: metadata düzeltmesi, kataloğa yeni bir seçmeli ders eklemek, doküman.
PR'a dosya (pdf, resim…) eklenirse CI reddeder.

## Kurallar
- Kişisel veri yok: sohbet ekran görüntüleri, telefon numarası, kimlik ve kişisel fotoğraflar yasak.
  Sınav ve ödev kağıtlarındaki isimler sorun değil.
- Telifli kitapların tamamını yükleme, link ver.
- Çalıştırılabilir dosyalar ve makrolu Office dosyaları (`.docm`, `.xlsm`) kabul edilmez. `.rar` ve `.7z` dosyalarını önce aç.
- Kendi notların `student-notes` türüne girer (isteğe bağlı katman; isteyen indirmez).
