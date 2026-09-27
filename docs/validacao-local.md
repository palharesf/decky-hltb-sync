# Validação local — 2026-09-27

Ambiente: Windows/PowerShell, Python 3.12, pnpm 10.30.0. Nenhum acesso a conta
HLTB e nenhuma instalação no Deck durante esses testes.

| Comando | Resultado |
| --- | --- |
| `pnpm test` | 23 testes Python + 3 testes JS passaram |
| `pnpm typecheck` | Passou |
| `pnpm build` | Passou; gerou `dist/index.js` |
| `python tools/demo.py` | Simulação: 3600 → 3630 s; releitura simulada confirmou |

Cobertura: suspensão e retomada, fechamento durante suspensão, eventos
duplicados, relógio/execução inválidos, ausência de importação retroativa,
checkpoint recuperado, lacunas de observação, schema futuro, preservação integral
dos campos não alterados, parser de página, progresso nulo, associação única,
drift remoto, autorização, offline antes de enviar, timeout antes/depois da
gravação simulada, queda após intenção persistida, bloqueio de repetição e
serialização das propostas do mesmo jogo, próxima sessão sobre baseline verificado,
divergência de notas na releitura. Sondagem JS testada com DOM sintético incluindo
cookie getter que falha se acessado, origem incorreta e ausência de login.

Não testado: hardware Steam Deck, eventos reais Steam/suspensão, arquivos em
SteamOS, navegador autenticado, HTML real da conta, IDs Vexx/PS2, cookies do
plugin, normalização do servidor, `/api/submit`, persistência real após queda de
energia e coexistência operacional com Playnite. Os testes não substituem esses
experimentos. Não há ainda um adaptador de captura de jogos nem transporte HLTB
de produção; o frontend apenas lista sessões.

Diagnóstico de rede: tentativa TCP limitada a 2,5 s em `192.168.0.6:22` não
estabeleceu conexão. Não houve sessão SSH, instalação, reinício, publicação,
alteração de controles/saves/emuladores ou escrita no HLTB.
