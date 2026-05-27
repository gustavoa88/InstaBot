# Content Carousel Platform

Aplicacao web para criar, revisar, renderizar e exportar carrosseis a partir de ideias inseridas pelo usuario.

## Funcionalidades Mantidas

* Cadastro de ideias de carrossel.
* Geracao de roteiro, legenda e hashtags com IA.
* Edicao de conteudo dos slides.
* Geracao de assets visuais.
* Renderizacao de imagens dos slides.
* Exportacao local em ZIP com imagens e metadados.
* Configuracao de chave OpenAI por usuario.
* Logs de execucao e limpeza de midias expiradas.

## Fluxo Atual

1. Criar uma ideia.
2. Gerar a estrutura dos slides.
3. Revisar textos, legenda e hashtags.
4. Gerar assets visuais quando necessario.
5. Renderizar os slides.
6. Exportar os arquivos gerados quando precisar usar fora da plataforma.

## Backend

* Python 3.12+
* FastAPI
* SQLAlchemy
* Alembic
* PostgreSQL
* Redis/Celery para tarefas internas
* OpenAI para texto e imagem

## Frontend

* React
* Vite
* TailwindCSS

## Variaveis Principais

```env
APP_ENV=development
APP_BIND_HOST=127.0.0.1
DATABASE_URL=postgresql://contentuser:contentpass@postgres:5432/contentdb
REDIS_URL=redis://redis:6379/0
OPENAI_MODEL=gpt-5-mini
OPENAI_IMAGE_MODEL=gpt-image-1-mini
STORAGE_PATH=/app/storage
PUBLIC_BASE_URL=
MEDIA_RETENTION_DAYS=30
```

## Exportacao ZIP

O endpoint de exportacao gera um arquivo ZIP em memoria com a seguinte estrutura:

```text
carousel_<id>_<timestamp>.zip
slides/
  01.png
  02.png
metadata.json
README.txt
```

O `metadata.json` contem titulo, legenda, hashtags e dados basicos dos slides.

## Testes

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests
PYTHONPYCACHEPREFIX=/tmp/ccp_pycache PYTHONPATH=backend .venv/bin/python -m compileall backend/app
```

## Nota De Escopo

A plataforma nao possui integracao externa de rede social, OAuth externo, fila de envio externo ou fluxo interno de agenda de envio. O uso dos arquivos exportados acontece manualmente fora do sistema.
