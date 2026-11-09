# gazi-bm-mf-notlar

Gazi Üniversitesi Bilgisayar Mühendisliği ders kaynakları deposu: slaytlar, ders notları, çıkmış sorular,
ödevler, lab föyleri ve öğrenci notları. Hepsi ders koduna göre düzenli, her dosyanın bir metadata kaydı var.
Depoyu AI agent'ları yönetiyor, her ekleme bir insan tarafından onaylanıyor.

*Course resource archive for Gazi University Computer Engineering, managed by AI agents with human review.
Agents: start with [`AGENTS.md`](AGENTS.md).*

## Yapı
```
catalog/            müfredat (curriculum.yaml), kaynak türleri (taxonomy.yaml), index.json
courses/<KOD>/      slides/ lecture-notes/ exams/ exam-solutions/ homework/ labs/ student-notes/ …
general/            derse ait olmayan, onaylanmış kaynaklar (staj, kariyer, genel kitaplar…)
tools/archive.py    ekleme, tarama, doğrulama ve indeks aracı
.agents/skills/     agent yönergeleri
```
Her dersin `README.md` dosyası, o dersteki bütün kaynakların tablosunu içerir (otomatik üretilir).

## İndirme seçenekleri
Öğrenci notları (el yazısı taramalar dahil) isteğe bağlı bir katmandır (`student-notes/` klasörleri).

| Sürüm | İçerik |
|---|---|
| **full** | her şey |
| **core** | öğrenci notları hariç her şey |

`core` sürümünü almak için:
```bash
git clone --filter=blob:none --no-checkout https://github.com/<owner>/gazi-bm-mf-notlar
cd gazi-bm-mf-notlar
git sparse-checkout set --no-cone '/*' '!/courses/*/student-notes/'
git checkout
```
Release sayfasında da her sürüm için hazır zip paketleri bulunur (`.github/workflows/release.yml`).

## Katkı
Elindeki dosyaları eklemek için [CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bak. En kolay yol: kendi AI agent'ına
"bu dosyaları gazi-bm-mf-notlar deposuna ekle" de ve depoyu göster; agent `.agents/skills/contributor-submit`
yönergesine göre bir PR ya da issue açar. Depo agent'ı inceler, bir insan onaylar.

## Gizlilik ve güvenlik
Sohbet kayıtları, telefon numaraları ve kişisel fotoğraflar depoya **girmez**. Bütün dosyalar tür, imza ve
antivirüs taramasından geçer. Ayrıntılar: [docs/SECURITY.md](docs/SECURITY.md).
