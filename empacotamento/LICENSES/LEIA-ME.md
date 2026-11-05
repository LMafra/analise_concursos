# Licenças dos componentes do executável

O concurso-analise empacotado leva junto, sem modificação:

| Componente | Licença | Onde está o texto |
|---|---|---|
| Python | PSF License | `LICENSES/python/` |
| Tesseract OCR | Apache 2.0 | `tesseract/licencas/` |
| Leptonica e bibliotecas de imagem (libpng, libjpeg, libtiff, libwebp, zlib, giflib, openjpeg) | BSD, IJG, libtiff e zlib | `tesseract/licencas/` |
| Modelo `por.traineddata` (tessdata_fast) | Apache 2.0 | `tesseract/licencas/` |
| NiceGUI | MIT | `LICENSES/nicegui-*/` |
| pywebview | BSD 3 | `LICENSES/pywebview-*/` |
| Demais pacotes Python (pandas, numpy, OpenCV, plotly, matplotlib, scikit-learn, pyarrow e outros) | as de cada pacote | `LICENSES/<pacote>-<versão>/` |
| Captura do TEC (`tec-erros/`) | a do repositório | `tec-erros/` |

As pastas `LICENSES/<pacote>-<versão>/` são geradas no build por `empacotamento/coletar_licencas.py`, a partir dos
arquivos de licença que cada pacote instala. As do Tesseract vêm junto com os binários, pelos scripts de
`empacotamento/tesseract/`.
