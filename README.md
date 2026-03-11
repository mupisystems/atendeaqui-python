# AtendeAqui SDK Python

SDK Python unificado para a plataforma AtendeAqui.

## Instalação

```bash
pip install atendeaqui
```

## Quick Start

```python
from atendeaqui import AtendeAquiClient

client = AtendeAquiClient(api_token="seu-bearer-token")

# Onboarding
flow = client.onboarding.get_structure(flow_key="uuid-do-flow", language="pt-BR")
progress = client.onboarding.start_flow(flow_key="uuid-do-flow", user_id="user-123", name="João Silva", email="u@example.com")
progress = client.onboarding.complete_step(flow_key="uuid-do-flow", user_id="user-123", step_key="welcome")
print(f"Progresso: {progress.completion_percentage}%")
```

## Autenticação

### Com api_token (recomendado)

O `api_token` é um Bearer token gerado no dashboard. Dá acesso a todos os módulos: clientes, onboarding (admin e progresso) e futuros módulos.

```python
client = AtendeAquiClient(api_token="seu-bearer-token")

# Clientes
client.clients.list()

# Onboarding — passa flow_key por operação
client.onboarding.start_flow(flow_key="uuid-do-flow", user_id="user-123")
client.onboarding.list_flows()
client.onboarding.get_analytics(slug="meu-flow")
```

### Com flow_key default (atalho para um único flow)

Se o seu sistema interage com um único flow, passe `flow_key` na inicialização. Ele será usado como default em todos os métodos de onboarding (pode ser sobrescrito por chamada).

```python
client = AtendeAquiClient(flow_key="f47ac10b-58cc-4372-a567-0e02b2c3d479")

# Usa o flow_key default — não precisa repetir
client.onboarding.get_structure()
client.onboarding.start_flow(user_id="user-123")

# Pode sobrescrever por chamada
client.onboarding.get_structure(flow_key="outro-flow-uuid")
```

### Com ambos (API admin + flow default)

```python
client = AtendeAquiClient(
    api_token="seu-bearer-token",
    flow_key="f47ac10b-58cc-4372-a567-0e02b2c3d479",
)
# Operações de progresso (usa flow_key default)
client.onboarding.start_flow(user_id="user-123")
# Operações admin (usa api_token)
client.onboarding.list_flows()
client.onboarding.get_analytics(slug="meu-flow")
```

## Módulos

### Clientes (requer api_token)

```python
admin = AtendeAquiClient(api_token="seu-bearer-token")

# Listar clientes
clientes = admin.clients.list(page=1, page_size=50)

# Criar cliente (client_id é gerado automaticamente se não fornecido)
novo = admin.clients.create(
    full_name="Acme Corp",
    email="contato@acme.com",
    phone="1133334444",
    identification_number="12.345.678/0001-90",
    type_identification="CNPJ",
)
print(novo.client_id)  # UUID gerado automaticamente

# Ou criar com ID do seu sistema (evita manter mapeamento de IDs)
novo = admin.clients.create(
    full_name="Acme Corp",
    email="contato@acme.com",
    client_id="meu-sistema-123",  # opcional: usa o ID do seu sistema local
)

# Detalhes do cliente
cliente = admin.clients.get(client_id=novo.client_id)

# Atualizar cliente
admin.clients.update(novo.client_id, full_name="Acme Corp Ltda", phone="1199998888")

# Equipe do cliente
team = admin.clients.get_team(novo.client_id)
for member in team:
    print(f"{member.full_name} (primary={member.is_primary})")

# Adicionar membro (cria usuário se não existir)
member = admin.clients.add_team_member(
    client_id=novo.client_id,
    user_email="joao@acme.com",
    is_primary=True,
    can_create_tickets=True,
)

# Atualizar permissões
admin.clients.update_team_member(novo.client_id, member.id, can_edit_client=True)

# Remover membro
admin.clients.remove_team_member(novo.client_id, member.id)
```

### Onboarding

```python
FLOW = "uuid-do-flow"

# Estrutura do flow
flow = client.onboarding.get_structure(flow_key=FLOW, language="pt-BR")

# Iniciar onboarding
progress = client.onboarding.start_flow(
    flow_key=FLOW,
    user_id="user-123",
    name="João Silva",
    email="user@example.com",
    metadata={"company": "Acme", "preferred_language": "pt-BR"},
)

# Completar steps
progress = client.onboarding.complete_step(
    user_id="user-123",
    flow_key=FLOW,
    step_key="welcome",
    step_data={"accepted_terms": True},
)

# Completar múltiplos steps (batch)
progress = client.onboarding.complete_steps(
    user_id="user-123",
    flow_key=FLOW,
    steps=[
        {"step_key": "config", "step_data": {"api_key": "xxx"}},
        {"step_key": "test"},
    ],
)

# Pular step opcional
progress = client.onboarding.skip_step(user_id="user-123", flow_key=FLOW, step_key="tour")

# Atualizar metadata (merge)
progress = client.onboarding.update_metadata(
    user_id="user-123",
    flow_key=FLOW,
    metadata={"plan": "pro"},
)

# Consultar progresso
progress = client.onboarding.get_progress(user_id="user-123", flow_key=FLOW)
print(progress.status)              # IN_PROGRESS
print(progress.steps_completed)     # ['welcome', 'config']
print(progress.step_data)           # {'welcome': {'accepted_terms': True}, ...}
print(progress.completion_percentage)  # 75
print(progress.flow_slug)           # 'onboarding-clientes'

# Ações no flow
client.onboarding.complete_flow(user_id="user-123", flow_key=FLOW)
client.onboarding.restart_flow(user_id="user-123", flow_key=FLOW)
client.onboarding.abandon_flow(user_id="user-123", flow_key=FLOW)

# Token para widget frontend
token = client.onboarding.get_widget_token(flow_key=FLOW, user_id="user-123", ttl=600)

# Admin: listar flows e analytics (requer api_token)
flows = client.onboarding.list_flows()
analytics = client.onboarding.get_analytics(slug="meu-flow")
progress_list = client.onboarding.list_progress(slug="meu-flow")
```

## Exemplos de Uso

### Fluxo completo com dados de perfil

Quanto mais dados você enviar no `metadata` e `step_data`, mais personalizados serão os e-mails automáticos enviados pelo sistema. O sistema de e-mails usa IA para gerar conteúdo baseado no perfil e caso de uso do cliente.

```python
from atendeaqui import AtendeAquiClient

client = AtendeAquiClient(flow_key="uuid-do-flow")

# 1. Iniciar o flow com metadata do usuário
#    Esses dados são usados pela IA para personalizar e-mails de boas-vindas
progress = client.onboarding.start_flow(
    user_id="empresa-456",
    name="João Silva",
    email="joao@agendapro.com.br",
    metadata={
        "company": "AgendaPro",
        "sector": "tecnologia",
        "role": "CTO",
        "plan": "professional",
        "preferred_language": "pt-BR",
    },
)
# >>> E-mail de boas-vindas é enviado automaticamente (se configurado)
# >>> A IA usa nome, empresa e cargo para personalizar a saudação

# 2. Completar etapa de perfil com caso de uso
#    step_data é JSON livre — envie tudo que descreve o cenário do cliente
progress = client.onboarding.complete_step(
    user_id="empresa-456",
    step_key="perfil",
    step_data={
        "uso_pretendido": "reuniões de vendas",
        "tamanho_equipe": "até 10 pessoas",
        "frequencia_uso": "diário",
        "integracao_desejada": "Google Calendar",
    },
)

# 3. Completar configuração técnica
progress = client.onboarding.complete_step(
    user_id="empresa-456",
    step_key="configuracao-api",
    step_data={
        "api_token": "EAAG...configurado",
        "provider": "google",
        "webhook_url": "https://agendapro.com.br/webhook",
    },
)

# 4. Completar múltiplos steps de uma vez
progress = client.onboarding.complete_steps(
    user_id="empresa-456",
    steps=[
        {
            "step_key": "convidar-equipe",
            "step_data": {
                "membros_convidados": 5,
                "emails": ["ana@agendapro.com.br", "pedro@agendapro.com.br"],
            },
        },
        {
            "step_key": "personalizar-agenda",
            "step_data": {
                "horario_inicio": "08:00",
                "horario_fim": "18:00",
                "duracao_padrao": "30min",
                "fuso_horario": "America/Sao_Paulo",
            },
        },
    ],
)

# 5. Completar o flow
client.onboarding.complete_flow(user_id="empresa-456")
```

### Integração com sistema existente (SaaS)

Exemplo de integração server-side: criar cliente + iniciar onboarding vinculado.

```python
from atendeaqui import AtendeAquiClient, NotFoundError

FLOW_KEY = "uuid-do-flow"

# api_token necessário para criar clientes
client = AtendeAquiClient(api_token="seu-bearer-token")


def on_client_signup(client_data: dict):
    """Chamado após o cadastro de um novo cliente no seu sistema."""

    # 1. Criar cliente no AtendeAqui usando o ID do seu sistema
    #    Isso evita manter um mapeamento separado de IDs
    novo_cliente = client.clients.create(
        full_name=client_data["company_name"],
        email=client_data["email"],
        client_id=client_data["id"],  # usa o ID do seu sistema local
    )

    # 2. Iniciar onboarding vinculado ao cliente
    progress = client.onboarding.start_flow(
        flow_key=FLOW_KEY,
        user_id=client_data["id"],
        name=client_data["name"],
        email=client_data["email"],
        metadata={
            "company": client_data.get("company_name", ""),
            "sector": client_data.get("industry", ""),
            "plan": client_data.get("plan", "free"),
        },
        client_id=novo_cliente.client_id,  # vincula onboarding ao cliente
    )

    return progress


def on_feature_configured(user_id: str, feature: str, config: dict):
    """Chamado quando o cliente configura uma feature no seu sistema."""

    step_map = {
        "api_setup": "configuracao-api",
        "team_invite": "convidar-equipe",
        "branding": "personalizar-marca",
    }

    step_key = step_map.get(feature)
    if not step_key:
        return

    try:
        progress = client.onboarding.complete_step(
            flow_key=FLOW_KEY,
            user_id=user_id,
            step_key=step_key,
            step_data=config,
        )
        return progress
    except NotFoundError:
        return None


def check_onboarding_status(user_id: str) -> dict:
    """Verifica o status do onboarding para exibir no dashboard."""

    try:
        progress = client.onboarding.get_progress(flow_key=FLOW_KEY, user_id=user_id)
        return {
            "status": progress.status,
            "percentage": progress.completion_percentage,
            "is_completed": progress.is_completed,
            "current_step": progress.current_step_title,
            "steps_done": progress.steps_completed,
        }
    except NotFoundError:
        return {"status": "NOT_STARTED", "percentage": 0}
```

### Widget frontend com token JWT

```python
from atendeaqui import AtendeAquiClient

FLOW_KEY = "uuid-do-flow"

# Server-side: gerar token seguro para o frontend
server_client = AtendeAquiClient(flow_key=FLOW_KEY)

# Em uma view/endpoint do seu backend:
def get_onboarding_token(request):
    token = server_client.onboarding.get_widget_token(
        user_id=request.user.external_id,
        client_id=request.user.client_id,
        ttl=600,  # 10 minutos
    )
    return {"token": token.token, "expires_in": token.expires_in}
```

### Atualizar metadata em tempo real

Use `update_metadata` para enriquecer o perfil do cliente conforme ele interage com o sistema. Esses dados são usados pela IA nos e-mails de lembrete e parabéns.

```python
# Quando o cliente atualiza o plano
client.onboarding.update_metadata(
    flow_key=FLOW_KEY,
    user_id="empresa-456",
    metadata={"plan": "enterprise", "seats": 50},
)

# Quando detectar a timezone do cliente
client.onboarding.update_metadata(
    flow_key=FLOW_KEY,
    user_id="empresa-456",
    metadata={"timezone": "America/Sao_Paulo", "locale": "pt-BR"},
)
```

### Admin: monitorar onboarding

```python
# Requer api_token (Bearer token)
admin_client = AtendeAquiClient(api_token="seu-bearer-token")

# Listar todos os flows
flows = admin_client.onboarding.list_flows()
for flow in flows:
    print(f"{flow['name']}: {flow['total_starts']} inícios, "
          f"{flow['completion_rate']}% conclusão")

# Analytics de um flow específico
analytics = admin_client.onboarding.get_analytics(slug="onboarding-clientes")
print(f"Taxa de conclusão: {analytics.completion_rate}%")
print(f"Tempo médio: {analytics.average_completion_time}s")
print(f"Em progresso: {analytics.in_progress}")
print(f"Abandonados: {analytics.abandoned}")

# Drop-off por etapa
for step_key, data in analytics.step_drop_off.items():
    print(f"  {data['title']}: {data['completion_rate']}% "
          f"({data['dropped']} desistiram)")

# Listar progresso de todos os usuários
progress_list = admin_client.onboarding.list_progress(
    slug="onboarding-clientes",
    page=1,
    page_size=100,
)
```

## Referência: step_data e e-mails automáticos

O sistema de automação de e-mails usa IA para gerar conteúdo personalizado. Quanto mais dados você enviar via `step_data` e `metadata`, melhor a personalização.

### Parâmetros diretos do `start_flow`

| Parâmetro | Exemplo | Uso |
|-----------|---------|-----|
| `flow_key` | `"f47ac10b-..."` | UUID público do flow (obrigatório se não definido no client) |
| `name` | `"João Silva"` | Saudação nos e-mails, busca no admin |
| `email` | `"joao@acme.com"` | Destinatário dos e-mails automáticos |
| `client_id` | `"uuid-do-cliente"` | Opcional. Vincula o onboarding ao cliente (para tickets de suporte) |

### Dados recomendados no `metadata` (start_flow)

| Campo | Exemplo | Uso nos e-mails |
|-------|---------|--------------------|
| `company` | `"AgendaPro"` | Contextualizar a empresa |
| `sector` | `"tecnologia"` | Adaptar linguagem ao setor |
| `role` | `"CTO"` | Tom e nível técnico adequado |
| `plan` | `"professional"` | Sugestões baseadas no plano |
| `preferred_language` | `"pt-BR"` | Idioma do e-mail |

### Dados recomendados no `step_data` (complete_step)

| Step | Campos sugeridos | Uso nos e-mails |
|------|------------------|--------------------|
| Perfil/Caso de uso | `uso_pretendido`, `tamanho_equipe`, `frequencia_uso` | "Como você vai usar para reuniões de vendas com 10 pessoas..." |
| Configuração técnica | `provider`, `webhook_url` | "Você já configurou a integração com Google Calendar..." |
| Equipe | `membros_convidados`, `emails` | "Você convidou 5 membros — falta apenas personalizar a agenda" |
| Personalização | `horario_inicio`, `horario_fim`, `duracao_padrao` | "Sua agenda está configurada para atendimentos de 30min..." |

> **Dica:** Campos com nomes como `token`, `password`, `secret`, `key` e `credential` são automaticamente mascarados nos prompts da IA por segurança.

## Tratamento de Erros

```python
from atendeaqui import (
    AtendeAquiClient,
    StepNotFoundError,
    NotFoundError,
    ValidationError,
    AtendeAquiError,
)

try:
    client.onboarding.complete_step(flow_key=FLOW_KEY, user_id="user-123", step_key="invalid")
except StepNotFoundError as e:
    print(f"Step não existe: {e.message}")
except NotFoundError as e:
    print(f"Não encontrado: {e.message}")
except ValidationError as e:
    print(f"Dados inválidos: {e.message}")
except AtendeAquiError as e:
    print(f"Erro [{e.code}]: {e.message}")
```

### Hierarquia

```
AtendeAquiError
├── AuthenticationError    # 401/403
├── NotFoundError          # 404
├── ValidationError        # 400
│   ├── StepNotFoundError
│   └── StepNotSkippableError
├── OriginNotAllowedError  # CORS
├── RateLimitError         # 429
└── ServerError            # 5xx
```

## Estrutura do Pacote

```
atendeaqui/
├── __init__.py          # AtendeAquiClient + exports
├── client.py            # Cliente principal
├── _http.py             # Transport HTTP compartilhado
├── exceptions.py        # Exceções compartilhadas
├── clients/             # Módulo de Clientes
│   ├── __init__.py      # ClientsModule
│   └── models.py        # Client, TeamMember
└── onboarding/          # Módulo de Onboarding
    ├── __init__.py      # OnboardingModule
    └── models.py        # FlowStructure, UserProgress, etc.
```

Novos módulos (tickets, knowledge_base, etc.) seguirão o mesmo padrão.

## Requisitos

- Python 3.10+
- requests >= 2.28

## Licença

MIT
