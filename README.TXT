# README.TXT

# Projeto: Content Carousel Automation Platform

## Objetivo

Criar uma aplicação web para gerar, revisar, aprovar, agendar e publicar carrosséis para Instagram a partir de ideias inseridas pelo usuário.

O sistema deve permitir que o usuário:

* Cadastre uma ideia de carrossel.
* Gere automaticamente textos, estrutura dos slides, legenda e hashtags usando IA.
* Gere imagens dos slides com layout padronizado.
* Revise o conteúdo gerado.
* Aprove ou rejeite o carrossel.
* Agende data e hora de publicação.
* Reagende publicações.
* Cancele publicações.
* Publique automaticamente no Instagram.
* Limpe automaticamente mídias expiradas.

---

# Stack sugerida

## Backend

* Python 3.12
* FastAPI
* SQLAlchemy
* Alembic
* Pydantic
* PostgreSQL
* Redis
* Celery
* Celery Beat

## Frontend

* React
* Vite
* TailwindCSS

## Geração de imagens

* Pillow
* HTML/CSS to Image
* Templates reutilizáveis
* OpenAI Images API
* DALL·E / GPT Image

### Estratégia de geração visual

O sistema deve suportar dois modos de geração de imagem:

#### 1. Renderização determinística

Responsável pela composição final dos slides.

Usada para:

* textos
* títulos
* logos
* identidade visual
* margens
* alinhamento
* tipografia
* elementos fixos do layout

Ferramentas sugeridas:

* Pillow
* HTML/CSS to Image
* Templates reutilizáveis

Objetivo:
Garantir consistência visual, previsibilidade e controle total do layout.

---

#### 2. Geração criativa com IA

Responsável pela geração de:

* fundos
* ilustrações
* imagens conceituais
* personagens
* metáforas visuais
* assets criativos

Ferramentas sugeridas:

* OpenAI Images API
* DALL·E
* GPT Image

Regras:

* Imagens geradas por IA não devem conter textos críticos.
* O texto final deve ser aplicado posteriormente pelo renderizador determinístico.
* Toda imagem gerada deve ser armazenada como asset do carrossel.
* O usuário deve aprovar imagens geradas antes da publicação.
* Imagens rejeitadas podem ser removidas pela rotina automática de limpeza.

---

### Pipeline visual sugerido

Ideia
↓
IA gera roteiro
↓
IA sugere conceito visual
↓
DALL·E / GPT Image gera assets criativos
↓
Pillow / HTML monta slide final
↓
Preview
↓
Aprovação
↓
Agendamento
↓
Publicação

## Infra

* Ubuntu Server 24.04
* Docker Compose
* Nginx
* PostgreSQL
* Redis

---

# Arquitetura MVP

Usuário
↓
Portal Web
↓
FastAPI
↓
PostgreSQL

Celery Worker
↓
Gera texto, legenda, hashtags e slides

Celery Beat
↓
Verifica posts agendados

Publicador
↓
Instagram Graph API

---

# Módulos da aplicação

## 1. Módulo de Ideias

Responsável por cadastrar a ideia inicial do carrossel.

Campos:

* título
* ideia original
* tema
* tom de voz
* público-alvo
* quantidade de slides
* observações adicionais

Status inicial:

RASCUNHO

---

## 2. Módulo de Geração com IA

A partir da ideia cadastrada, o sistema deve gerar:

* título do carrossel
* estrutura dos slides
* texto principal de cada slide
* observação visual de cada slide
* legenda para Instagram
* hashtags
* CTA final

Após a geração, o status deve mudar para:

AGUARDANDO_APROVACAO

---

## 3. Módulo de Slides

Cada carrossel deve conter vários slides.

Cada slide deve ter:

* número do slide
* título
* texto principal
* texto secundário opcional
* observação visual
* caminho da imagem gerada
* configuração visual em JSONB

---

## 4. Módulo de Aprovação

O usuário deve conseguir:

* visualizar o carrossel completo
* editar textos dos slides
* editar legenda
* editar hashtags
* aprovar
* rejeitar
* solicitar regeneração

Status possíveis:

RASCUNHO
GERANDO
AGUARDANDO_APROVACAO
APROVADO
REJEITADO
AGENDADO
CANCELADO
PUBLICADO
ERRO_PUBLICACAO

---

## 5. Módulo de Agendamento

Após aprovação, o usuário informa:

* data da publicação
* hora da publicação
* plataforma

O status deve mudar para:

AGENDADO

---

## Funcionalidades adicionais do agendamento

O sistema deve permitir:

* reagendar publicações já agendadas
* cancelar agendamentos
* alterar legenda antes da publicação
* alterar hashtags antes da publicação
* alterar horário até o momento anterior da execução

---

## Regras de reagendamento

### RF008 — Reagendamento

O usuário deve conseguir alterar:

* data
* hora
* plataforma

de uma publicação com status:

AGENDADO

---

### RF009 — Bloqueio pós-publicação

Publicações com status:

PUBLICADO

não podem ser reagendadas.

---

### RF010 — Auditoria de reagendamento

Toda alteração de agendamento deve registrar:

* usuário responsável
* data/hora anterior
* nova data/hora
* timestamp da alteração

---

## 6. Módulo Publicador

O publicador deve verificar periodicamente posts com:

status = 'AGENDADO'
agendado_para <= now()

Então deve publicar no Instagram.

Após sucesso:

PUBLICADO

Após erro:

ERRO_PUBLICACAO

O erro deve ser gravado no banco.

---

# Banco de dados

## Tabela `carrossel`

```sql
CREATE TABLE carrossel (
    id BIGSERIAL PRIMARY KEY,
    titulo VARCHAR(200),
    ideia_original TEXT NOT NULL,

    status VARCHAR(50) NOT NULL DEFAULT 'RASCUNHO',

    tema VARCHAR(100),
    tom VARCHAR(100),
    publico_alvo VARCHAR(150),
    quantidade_slides INT DEFAULT 7,

    legenda TEXT,
    hashtags TEXT[],

    prompt_config JSONB,
    ia_resultado JSONB,

    aprovado BOOLEAN DEFAULT FALSE,
    aprovado_em TIMESTAMP,
    agendado_para TIMESTAMP,
    publicado_em TIMESTAMP,

    erro_publicacao TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Tabela `carrossel_slide`

```sql
CREATE TABLE carrossel_slide (
    id BIGSERIAL PRIMARY KEY,
    carrossel_id BIGINT REFERENCES carrossel(id) ON DELETE CASCADE,

    numero_slide INT NOT NULL,
    titulo TEXT,
    texto_principal TEXT,
    texto_secundario TEXT,
    observacao_visual TEXT,

    imagem_path TEXT,
    imagem_url TEXT,

    layout_config JSONB,

    aprovado BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Tabela `publicacao`

```sql
CREATE TABLE publicacao (
    id BIGSERIAL PRIMARY KEY,
    carrossel_id BIGINT REFERENCES carrossel(id) ON DELETE CASCADE,

    plataforma VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'AGENDADO',

    agendado_para TIMESTAMP NOT NULL,
    publicado_em TIMESTAMP,

    external_post_id TEXT,
    resposta_api JSONB,
    erro TEXT,

    reagendado BOOLEAN DEFAULT FALSE,
    reagendado_em TIMESTAMP,
    agendamento_anterior TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Tabela `log_execucao`

```sql
CREATE TABLE log_execucao (
    id BIGSERIAL PRIMARY KEY,
    carrossel_id BIGINT,
    etapa VARCHAR(100),
    status VARCHAR(50),
    mensagem TEXT,
    detalhes JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

# Regras técnicas

## RT001

Não salvar imagens diretamente no PostgreSQL.

Salvar imagens em disco e armazenar apenas:

* caminho local
* URL pública
* metadados necessários

no banco de dados.

---

## Política de retenção de imagens

O sistema deve possuir rotina automática de limpeza para remover imagens que:

* pertençam a carrosséis rejeitados
* pertençam a carrosséis cancelados
* pertençam a carrosséis publicados há mais de X dias
* estejam órfãs (sem referência válida no banco)

A rotina deve:

* apagar os arquivos físicos
* registrar log da remoção
* preservar integridade do banco

A quantidade de dias para retenção após publicação deve ser configurável.

Exemplo:

```env
MEDIA_RETENTION_DAYS=30
```

---

## RT001.1 — Limpeza automática de mídia

Deve existir um worker/scheduler responsável por:

* identificar mídias expiradas
* validar se ainda estão em uso
* apagar arquivos físicos
* atualizar registros necessários
* registrar logs de limpeza

A execução deve ocorrer periodicamente.

Exemplo:

* diariamente às 03:00

---

## RT002

Usar JSONB para:

* resposta bruta da IA
* configurações de prompt
* configurações visuais dos slides
* resposta da API externa
* prompts utilizados no DALL·E / GPT Image
* parâmetros de geração visual
* histórico de variações de imagem
* metadados dos assets criativos

---

## RT003

Usar colunas relacionais para:

* status
* título
* data de agendamento
* data de publicação
* aprovação
* plataforma

---

## RT004

Toda tarefa pesada deve rodar em worker Celery, não diretamente na requisição da API.

---

## RT005 — Controle de concorrência

Evitar que o mesmo carrossel seja:

* gerado duas vezes simultaneamente
* publicado duas vezes
* reagendado durante publicação

Implementar locks ou controle transacional.

---

## RT006 — Versionamento de conteúdo

O sistema deve manter histórico das alterações relevantes:

* legenda
* hashtags
* textos dos slides
* agendamento

---

## RT007 — Fail-safe de publicação

Se ocorrer erro durante publicação:

* registrar erro detalhado
* não apagar mídias
* permitir nova tentativa manual
* evitar publicação duplicada

---

# Endpoints principais

## Ideias

```http
POST /carrosseis
GET /carrosseis
GET /carrosseis/{id}
PUT /carrosseis/{id}
DELETE /carrosseis/{id}
```

---

## Geração

```http
POST /carrosseis/{id}/gerar
POST /carrosseis/{id}/regenerar
```

---

## Slides

```http
GET /carrosseis/{id}/slides
PUT /slides/{slide_id}
```

---

## Aprovação

```http
POST /carrosseis/{id}/aprovar
POST /carrosseis/{id}/rejeitar
```

---

## Agendamento

```http
POST /carrosseis/{id}/agendar
PUT /publicacoes/{id}/reagendar
POST /publicacoes/{id}/cancelar
```

---

## Publicação

```http
POST /carrosseis/{id}/publicar-agora
GET /publicacoes
GET /publicacoes/{id}
```

---

# Estrutura de pastas

```text
content-carousel-platform/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routes/
│   │   ├── services/
│   │   │   ├── ai_service.py
│   │   │   ├── image_service.py
│   │   │   ├── instagram_service.py
│   │   │   └── scheduler_service.py
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   ├── tasks_generation.py
│   │   │   └── tasks_publication.py
│   │   └── utils/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── services/
│   │   └── App.jsx
│   └── package.json
│
├── storage/
│   └── carrosseis/
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# Variáveis de ambiente

```env
APP_ENV=development
DATABASE_URL=postgresql://user:password@postgres:5432/contentdb
REDIS_URL=redis://redis:6379/0

OPENAI_API_KEY=
OPENAI_MODEL=

INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_USER_ID=
FACEBOOK_PAGE_ID=

STORAGE_PATH=/app/storage
PUBLIC_BASE_URL=

MEDIA_RETENTION_DAYS=30
```

---

# Estrutura sugerida para assets gerados por IA

```text
/storage/carrosseis/
├── 2026/
│   └── 05/
│       └── carrossel_0001/
│           ├── assets_ia/
│           │   ├── conceito_01.png
│           │   ├── conceito_02.png
│           │   └── fundo_01.png
│           │
│           ├── slides_finais/
│           │   ├── slide_01.png
│           │   ├── slide_02.png
│           │   └── slide_03.png
│           │
│           └── metadata.json
```

---

# Melhorias futuras sugeridas

## Funcionalidades futuras

* Multiusuário
* Multiempresa
* MultiInstagram
* Biblioteca de templates
* Versionamento visual de slides
* Integração LinkedIn
* Integração YouTube Shorts
* Dashboard de métricas
* Analytics de engajamento
* Banco de ideias
* Sugestão automática de temas
* Pipeline IA → postagem
* Aprovação por múltiplos usuários
* Sistema de permissões
* Notificações via WhatsApp/Telegram

---

# MVP esperado

O MVP deve entregar:

* Cadastro de ideia
* Geração textual do carrossel com IA
* Criação dos registros de slides no banco
* Tela de revisão
* Aprovação manual
* Reagendamento
* Cancelamento
* Agendamento
* Worker de publicação mockado
* Logs de execução
* Limpeza automática de mídia

A publicação real no Instagram pode ser implementada como segunda etapa.

---

# Critérios de aceite

O projeto será considerado funcional quando:

* For possível cadastrar uma ideia.
* O sistema gerar os slides automaticamente.
* O usuário conseguir visualizar e editar os slides.
* O usuário conseguir aprovar o carrossel.
* O usuário conseguir reagendar publicação.
* O usuário conseguir cancelar publicação.
* O usuário conseguir agendar publicação.
* O worker identificar o conteúdo agendado.
* O sistema registrar logs de cada etapa.
* O sistema limpar mídias expiradas.
* O conteúdo aprovado nunca for publicado sem ação manual do usuário.
* O sistema evitar publicações duplicadas.
