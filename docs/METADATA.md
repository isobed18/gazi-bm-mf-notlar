# Metadata sidecar (`<file>.meta.yaml`)

Written by `archive.py place`; never by hand (except `topics:` by the `exam-matching` skill).

```yaml
file: BM218_exam_2023-fall_midterm.pdf   # normalized name: <CODE>_<kind>_<year-term>_<exam_type>_w<week>_<slug>.<ext>
sha256: 64-hex                           # content hash; duplicates are refused
course: BM218                            # absent for general/ resources
kind: exam                               # catalog/taxonomy.yaml kinds, or general:<category>
title: Vize
year: 2023                               # academic year start (2023 = 2023-2024)
term: fall                               # fall | spring | summer
exam_type: midterm                       # midterm | final | makeup | quiz | resit | sample
week: 5
language: tr                             # tr | en | mixed
handwritten: false
topics: [Dinamik Programlama, Greedy]
related: courses/BM218/exams/…           # e.g. the exam of a solution
source: {type: whatsapp, ref: bm-2023-sinif}   # whatsapp | drive | upload | instructor | self | unknown
contributor: github-username             # for PR contributions
added: '2026-11-09'
status: approved                         # approved | needs-review | deprecated
scan: {verdict: ok, antivirus: clamscan:clean}
notes: free text from the maintainer
```
