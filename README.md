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

## Dosyalar nerede?
Git deposunda sadece metadata, notlar ve araçlar var. **Dosyaların kendisi (PDF, slayt, fotoğraf) Google Drive
aynasında** ve klasör yapısı depoyla aynı: `courses/<KOD>/exams/…`. Ayrıntılar: [docs/STORAGE.md](docs/STORAGE.md).

Öğrenci notları (el yazısı taramalar dahil) isteğe bağlı bir katmandır (`student-notes/` klasörleri):

| Sürüm | İçerik | Nasıl |
|---|---|---|
| **full** | her şey | Drive klasörünün tamamı veya `archive.py storage-pull` |
| **core** | öğrenci notları hariç | `student-notes/` klasörlerini atla veya `archive.py storage-pull --variant core` |

## Katkı
Elindeki dosyaları eklemek için [CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bak. En kolay yol: kendi AI agent'ına
"bu dosyaları gazi-bm-mf-notlar deposuna ekle" de ve depoyu göster; agent `.agents/skills/contributor-submit`
yönergesine göre bir PR ya da issue açar. Depo agent'ı inceler, bir insan onaylar.

## Gizlilik ve güvenlik
Sohbet kayıtları, telefon numaraları ve kişisel fotoğraflar depoya **girmez**. Bütün dosyalar tür, imza ve
antivirüs taramasından geçer. Ayrıntılar: [docs/SECURITY.md](docs/SECURITY.md).
