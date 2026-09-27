# Referências conferidas em 2026-09-27

Clones consultados por código; Playnite e PlayTime foram comparados com o HEAD
remoto após fetch. Demais referências foram clonadas novamente em `.local/`.

| Projeto | Commit | Evidência |
| --- | --- | --- |
| [Template oficial](https://github.com/SteamDeckHomebrew/decky-plugin-template/tree/90d0780e882a17f5714fc6de044c645f22608290) | `90d0780` | `package.json`, `main.py`, `decky.pyi`, Rollup, tsconfig e distribuição |
| [Playnite HLTB](https://github.com/Lacro59/playnite-howlongtobeat-plugin/tree/809c1890b0ce27942fd92c9b50ae7e38a8c89e30) | `809c189` | C#, licença MIT, serviços e EditData |
| [PlayTime](https://github.com/0u73r-h34v3n/SDH-PlayTime/tree/64d5faf8127f7e8588c8d26fae4567d58dc3f4f0) | `64d5faf` | `src/app/middleware.ts`, `middlewares/sleep.ts`, `SessionPlayTime.ts`; BSD-3-Clause |
| [HLTB for Deck](https://github.com/morwy/hltb-for-deck/tree/f5d203f9a7af8335f02f9925f9365c48c130a518) | `f5d203f` | `src/hooks/HltbApi.ts`, consulta e bootstrap de busca; MIT |
| [Plugin database](https://github.com/SteamDeckHomebrew/decky-plugin-database/tree/0bd244f2bd0c2c5bfd6d3904efa336dd1f001cd3) | `0bd244f` | README: submissão via PR/submódulo e referência à revisão do catálogo |

No Playnite, `source/Services/HowLongToBeatApi.cs` define `/submit/edit/{0}` e
`/api/submit` (linhas 505–506), lê `props.pageProps.editData` de `__NEXT_DATA__`
em `GetEditData` (~3345), abre WebView para login (~2844), extrai cookies após
fechar e verifica `hltb_alive` antes do envio (~3671). O POST serializa EditData
com Origin/Referer. Não é um contrato público do HLTB, nem prova de funcionamento
do mesmo fluxo no Deck.

`source/Models/Api/EditData.cs` define `general.progress` como objeto
hours/minutes/seconds anuláveis, além de notas, avaliações, listas, plataforma,
datas e outros tempos. Nosso parser mantém o dicionário integral, sem reconstruir
apenas campos conhecidos.

`HowLongToBeatDatabase.cs`, `GetAggregatedPlaytime` (~1843), soma Playtime local
dos jogos associados ao mesmo ID HLTB. `SetCurrentPlayTime` (~1925 e ~2170)
atribui esse total a `General.Progress`, condicionado às opções de sincronização.
Também pode escrever avaliação e listas conforme configuração. Portanto o risco
de sobrescrita não é apenas hipotético.

PlayTime observa diferenças em `SteamUIStore.RunningApps`, emite início/fim e
possui seleção de mecanismos de suspensão: System, User ou observáveis internos.
Esses nomes não foram confirmados na versão instalada do Deck.

HLTB for Deck usa token de bootstrap para **busca**, que não deve ser confundido
com autenticação da conta. O código de consulta examinado não implementa o fluxo
de edição/envio pessoal. Não foi feita uma busca exaustiva de todos os plugins
existentes; não afirmamos inexistência de outra integração.

Nosso código é original MIT. Configuração de build derivada do template BSD:
licença integral preservada ao final de LICENSE. Nenhum código PlayTime,
Playnite ou HLTB for Deck foi transplantado. As fontes orientaram o desenho.
