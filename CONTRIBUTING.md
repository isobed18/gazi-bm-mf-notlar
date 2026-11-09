# Katkı rehberi / Contributing

## Kısa yol: agent ile
1. Depoyu klonla, kendi agent'ını (Claude Code, Codex, Gemini/agy…) depo klasöründe aç.
2. "Şu dosyaları depoya ekle: …" de. Agent `AGENTS.md` ve `.agents/skills/contributor-submit` yönergelerini izleyerek:
   dosyaları tarar, doğru derse ve türe yerleştirir, metadata yazar ve PR açar.
3. Depo agent'ı PR'ı inceler ve yorum yazar. Bir insan onaylarsa birleştirilir; site ve indeks kendiliğinden güncellenir.

## Elle
```bash
pip install -r tools/requirements.txt
git checkout -b add/BM218-2023-sinavlar
python -X utf8 tools/archive.py intake ~/Downloads/vize.pdf --source upload:<github-kullanici-adin>
python -X utf8 tools/archive.py place inbox/<batch>/files/vize.pdf --course BM218 --kind exam --year 2023 --term fall --exam-type midterm --title "Vize"
python -X utf8 tools/archive.py validate && python -X utf8 tools/archive.py index
git add courses catalog && git commit -m "add(BM218): 2023 güz vize" && git push
```
Sonra PR şablonunu doldur.

Dosyanın hangi derse ait olduğundan emin değilsen PR yerine **"Kaynak önerisi" issue'su** aç ve dosyayı ekle;
yerini depo agent'ı önerir.

## Kurallar
- Kişisel veri yok: sohbet ekran görüntüleri, telefon numarası, kimlik ve kişisel fotoğraflar yasak.
  Sınav ve ödev kağıtlarındaki isimler sorun değil.
- Telifli kitapların tamamını yükleme, link ver.
- Çalıştırılabilir dosyalar ve makrolu Office dosyaları (`.docm`, `.xlsm`) kabul edilmez. `.rar` ve `.7z` dosyalarını önce aç.
- PR başına en fazla ~50 dosya veya 200 MB. Mümkünse her PR tek bir ders için olsun.
- Kendi notların `student-notes` türüne girer (isteğe bağlı katman; isteyen indirmez).
