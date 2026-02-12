# OCR Lab — Marcador de Áreas + Pré-processamento + OCR Reprodutível (PDF/Imagem)
<img width="481,6" height="365,6" alt="image" src="https://github.com/user-attachments/assets/2c9d8779-ed08-46a5-ba8b-7e17da218bb6" />
<img width="481,6" height="365,6" alt="image" src="https://github.com/user-attachments/assets/d7c3adaa-e467-4574-9727-e5b10d3fadf1" />
<img width="481,6" height="365,6" alt="image" src="https://github.com/user-attachments/assets/d1bf6aa9-3dcc-4dd1-9c77-2898eff38a9b" />
<img width="481,6" height="365,6" alt="image" src="https://github.com/user-attachments/assets/6747126c-337f-4fb4-8abf-d88619b95b86" />
<img width="437" height="851" alt="image" src="https://github.com/user-attachments/assets/7226d652-300c-4d4f-9acb-ed6ff0021f69" />



Ferramenta desktop para **anotar regiões (retângulos) em páginas de PDF ou imagens**, testar **pré-processamentos** e executar **OCR com Tesseract** de forma interativa.  
O objetivo é reduzir tentativa-e-erro e gerar um **artefato reprodutível** (CSV + projeto JSON) que pode ser usado diretamente em scripts Python de automação.

## Por que este projeto existe?

OCR em documentos reais varia muito por:
- qualidade do scan, ruído, resolução, fontes
- tabelas, linhas, carimbos, fundos
- diferentes campos do mesmo documento exigindo parâmetros diferentes

Este app funciona como um **laboratório**: você define regiões, ajusta parâmetros até o OCR ficar bom e salva um **perfil** (receita). Depois exporta as coordenadas + o perfil usado, para rodar OCR em lote em pipelines.

## Funcionalidades

### Anotação de Regiões
- Abrir **PDF** (multi-página) ou **imagem**
- Desenhar **múltiplos retângulos** por página
- Nomear/renomear retângulos
- Excluir retângulos (Delete)
- Navegação por páginas (setas e slider)
- **Zoom** (Ctrl+wheel, botões e atalhos) com **persistência de zoom** ao trocar de página

### OCR Interativo (Tesseract)
- Preview do **recorte original**
- Preview do **recorte processado**
- Pré-processamentos configuráveis:
  - scale (2x, 3x…)
  - grayscale
  - invert
  - threshold (Otsu / Adaptive / none)
  - blur / sharpen
  - morphology (open / close)
- OCR com:
  - idioma (`lang`)
  - whitelist/blacklist
- Resultado do OCR exibido no app
- Confiança média (quando disponível via `image_to_data`)

### Perfis OCR (reprodutibilidade)
- Salvar parâmetros como **perfil** nomeado (ex.: `padrao_portaria`, `numero_processo`)
- Trocar rapidamente entre perfis
- Projeto JSON persiste:
  - arquivo fonte
  - página atual
  - zoom/posição da visualização
  - retângulos (normalizados 0–1 por página)
  - perfis OCR + perfil ativo

### Exportação
- Exportar **CSV** com:
  - arquivo, página, label
  - coordenadas normalizadas e em pixels
  - dimensões da imagem renderizada
  - `ocr_profile` (perfil ativo usado)

## Instalação

### Requisitos
- Python 3.10+ (recomendado)
- Windows / Linux (testado principalmente em Windows)
- Tesseract OCR instalado (para OCR)

### Dependências Python
```bash
pip install -r requirements.txt
