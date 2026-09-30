# Third-party notices

This repository's own code and documents are covered by [LICENSE](LICENSE). The material below belongs to others and keeps its own licence or terms.

## Python dependencies (installed from PyPI, not included in this repository)

Versions are pinned in `requirements.txt`; licences are as declared in each package's metadata.

| Package | Version | Licence |
|---|---|---|
| numpy | 2.4.6 | BSD-3-Clause (bundled parts: 0BSD, MIT, Zlib, CC0-1.0) |
| opencv-python-headless | 5.0.0.93 | Apache-2.0 (OpenCV); the wheel also bundles third-party libraries under their own licences |
| colour-science | 0.4.7 | BSD-3-Clause |
| scipy | 1.17.1 | BSD-3-Clause |
| cryptography | 48.0.0 | Apache-2.0 OR BSD-3-Clause |
| jcs | 0.2.1 | Apache-2.0 |
| scikit-learn | 1.9.1 | BSD-3-Clause |
| pillow | 12.3.0 | MIT-CMU |
| pytest | 9.1.1 | MIT |

All of these licences permit use in this project.

## Files included in this repository

| Path | What it is | Source and terms |
|---|---|---|
| `ftr-reference/tools/attestation_samples/EC_StrongBox/`, `EC_TEE/` | Sample Android key-attestation certificate chains, used only in tests | [google/android-key-attestation](https://github.com/google/android-key-attestation), `src/test/resources/pem/`, Apache-2.0, © Google LLC |
| `ftr-reference/tools/attestation_samples/google_attestation_roots.pem` | Google's published hardware-attestation root certificates | [developer.android.com: key attestation](https://developer.android.com/privacy-and-security/security-key-attestation) |
| `ftr-reference/tools/attestation_samples/revocation_status.json` | Snapshot of Google's attestation revocation list | https://android.googleapis.com/attestation/status |
| `docs/sources/NIJ_Standard_0604_01_extracted.txt`, `ftr-reference/docs/research/data/nij0604_table1.csv` | Colour table extracted from NIJ Standard-0604.01, *Color Test Reagents/Kits for Preliminary Identification of Drugs of Abuse* | US Department of Justice publication, a work of the US Government |
| `ftr-reference/nddk.py` (colour values) | Approximate colours sampled from the printed charts of NCB's Narcotic Drugs Detection Kit (Figs 8.12–8.16) | NICFS, *A Forensic Guide for Crime Investigators*, ch. 8. Only measured colour values are used; the guide itself is not redistributed |
| `docs/deck/` (template graphics) | SIH 2026 idea-presentation template: logos and layout | Provided by Smart India Hackathon for idea submissions |

## Data used at run time from dependencies

The camera-sensor model, illuminant spectra and ColorChecker reference values come from datasets bundled with colour-science (BSD-3-Clause), which cites the original publications.

## Legal sources

Court judgments, statutes, rules and government statistics cited in the documents are referenced by citation and link (see `docs/sources/SOURCES.md`). Third-party PDFs are not redistributed.
