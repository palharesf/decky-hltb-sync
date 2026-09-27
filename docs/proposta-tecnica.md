# Proposta técnica — piloto Vexx

Estado em 2026-09-27: implementação local inicial, sem instalação e sem acesso
autenticado ao HLTB. O primeiro marco funcional **ainda não foi atingido**.

## Arquitetura

Um repositório com entrada `main.py`, módulos Python em `py_modules/hltb_sync`,
frontend React/TypeScript e build `@decky/rollup`, seguindo o template oficial.
SQLite e biblioteca padrão Python; sem serviço remoto próprio. O frontend inicial
mostra somente estado. O núcleo recebe eventos normalizados e um transporte
injetável; ainda faltam os adaptadores reais Steam/HLTB.

No Deck, persistência em `DECKY_PLUGIN_SETTINGS_DIR/private`, diretório 0700 e
arquivo 0600 no Linux; no desenvolvimento, somente `.local/`. Não expor o banco
no diretório servido de assets. Não registrar payloads, HTML, cookies ou exceções
de rede que possam carregar dados privados. Não implementar extração de cookies
do navegador, Playnite ou CDP sem autorização específica.

## Autenticação e leitura primeiro

O login será feito pelo usuário no site HTTPS do HLTB, em navegador no próprio
Deck. Abrir um navegador **não** autentica o Python do Decky: não há OAuth/API
pública confirmada e as sessões dos dois processos não são intercambiáveis.

Primeira sondagem revisável: `tools/browser-read-probe.js`, executado manualmente
na página `/submit/edit/{submissionId}` depois do login. Só lê o DOM existente;
não usa fetch, não acessa cookies e não envia nada ao HLTB. Exporta título,
plataforma, progresso e nomes dos campos, excluindo os valores de notas e dados
da conta. É diagnóstico, não prova de acesso autenticado pelo backend nem
snapshot completo utilizável para envio. Testado somente com DOM sintético.

Depois da sondagem, escolher e validar um canal no Deck: navegador dedicado
controlado localmente que faça requisições na própria origem, ou transferência
explicitamente autorizada da sessão criada para o plugin para um cookie jar
privado. Não há implementação desse canal nesta versão. A decisão depende das
capacidades reais do navegador/Decky instalado; não adicionar browser runtime ou
framework antes de verificar. Uma solução que exija console a cada sessão não
atende à automação final.

## Associação e contagem

Associação explícita: AppID do atalho → conta HLTB + gameId + submissionId +
plataforma. Confirmar no Deck o atalho direto do Vexx e no site `PlayStation 2`.
O AppID previamente informado não está fixado no produto. O núcleo recusa dois
atalhos para o mesmo registro no piloto. Não criar submissão automaticamente.
Steam/Epic/GOG/emuladores serão observados pelo atalho Steam, sem integração com
launchers externos. ES-DE permanece fora do piloto: observar seu processo não
identifica o jogo emulado.

O adaptador futuro deve observar `RunningApps`, eventos de suspensão/retomada e
mandar checkpoints a cada 10 s, serializados, com UUID estável para repetição de
um evento e identificador da execução. Usar relógio monotônico do backend Linux,
que exclui suspensão, além dos eventos explícitos. Não usar totais históricos
Steam nem horários civis para calcular duração. Diferenciar suspensão de saída:
suspender fecha intervalo ativo, retomar abre outro, sair fecha a sessão.

SQLite usa transações, WAL, synchronous FULL, IDs únicos e fila persistente.
Reinício preserva somente os intervalos confirmados, marcando a sessão aberta
como interrompida/precisa de atenção. Não inventar tempo no período sem observação.
Uma lacuna ativa acima de 30 s também exige atenção. Isso pode subcontar até o
último checkpoint; é uma limitação explícita do protótipo. Recuperação assistida
e buffer de eventos ainda precisam de interface e validação no Deck.

## Política de conflito, envio e Playnite

**Padrão: envio manual; automático indisponível.** O Playnite atual pode atribuir
o total agregado de jogos locais associados ao mesmo HLTB a `General.Progress`.
Somar o delta Deck ao remoto não impede uma sobrescrita posterior pelo PC.

Para automação futura, escolher um único escritor para esse registro: desativar
no Playnite o envio de tempo/status correspondente (o usuário faz essa escolha;
não alteraremos suas configurações). Sessões PC precisam de importação explícita
ou de um protocolo comum de contribuições por dispositivo, ainda inexistente.
Se mantiver ambos como escritores, permanecer em modo manual; não há garantia
de convergência. `max(totalPC,totalDeck)` também perde contribuições independentes.

1. Ler registro completo e conferir identidade/plataforma com a associação.
2. Se divergir do snapshot da associação/última confirmação, interromper para
   revisão; nunca restaurar silenciosamente o maior total nem somar novamente.
3. Preparar uma proposta imutável por sessão encerrada, anterior + segundos
   inteiros locais. Preservar todos os campos, inclusive desconhecidos. Alterar
   somente hours/minutes/seconds de `general.progress`; não mudar listas,
   conclusão, notas, avaliações, plataforma, datas nem tempos de conclusão.
4. Apresentar anterior/proposto para autorização específica. Reler imediatamente
   antes do envio; qualquer alteração bloqueia a proposta.
5. Persistir intenção `sending` antes da chamada. Em timeout, erro HTTP, resposta
   inesperada ou falha do processo: `uncertain` / precisa de atenção. Nunca
   reenviar automaticamente nem permitir outra operação desse jogo.
6. Reler registro completo. Igual ao proposto confirma o estado remoto observado
   e marca a sessão sincronizada atomicamente. Isso não prova quem escreveu.
   Igual ao anterior **não prova** que o envio falhou (pode haver sobrescrita).
   Qualquer diferença mantém bloqueio. Resolução manual ainda não implementada.

Não existe garantia de entrega exatamente uma vez. Sem CAS/ETag ou chave de
idempotência confirmados, há uma janela entre leitura e escrita na qual outro
cliente pode alterar o registro. Preservação é testada no payload local; não é
garantia de preservação em concorrência no servidor. Comparação integral é
deliberadamente conservadora: normalização de campos pelo HLTB pode exigir
atenção mesmo quando o tempo foi salvo. Não relaxar a comparação sem evidência.

## Portões do piloto

1. Disponibilidade SSH e diagnóstico de leitura: porta 22 do último IP não
   respondeu nesta execução. AppID, processos e capacidades não confirmados.
2. Login manual no navegador e sondagem do registro existente, sem senha no chat.
3. Validar canal autenticado local e registrar snapshot completo privado.
4. Confirmar associação Vexx/PS2 e preparar pacote revisável. Pedir autorização
   para instalação; testar fora de uma sessão de jogo, sem reiniciar durante jogo.
5. Capturar sessão real, incluindo suspensão, e apresentar anterior/proposto.
6. Pedir autorização específica para um envio real, depois reler e comparar.
7. Só considerar automático após sucesso, política Playnite escolhida e testes
   reais de retomada, expiração de login e rede indisponível.

Não publicar GitHub/catálogo neste marco. Empacotamento deverá incluir main.py,
py_modules, dist/index.js, metadados, README e licenças, excluindo `.local/`.
