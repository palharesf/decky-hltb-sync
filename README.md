# HLTB Sync for Deck

Protótipo Decky para registrar sessões locais e preparar atualizações conservadoras
do tempo no HowLongToBeat. Nosso código é MIT; créditos do template em LICENSE.

**Ainda não pronto para uso no Deck.** Autenticação real, captura Steam, associação
visual, instalação e envio HLTB não foram validados/implementados. A interface
inicial apenas consulta o banco. Não há transporte de escrita de produção.

Implementado localmente: SQLite persistente, estados de sessão, suspensão,
recuperação conservadora, associação explícita no núcleo, propostas preservando
campos, protocolo de envio com transporte simulado e bloqueio de reenvios incertos.

```powershell
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm build
python tools/demo.py
```

Requer Python 3.11+ e Node.js com pnpm. O lockfile foi gerado com pnpm 10; o
template recomenda pnpm 9 para submissão ao catálogo, ainda fora deste marco.
A demo usa somente dados sintéticos e cria banco temporário dentro de `.local/`.

- [Proposta técnica e política Playnite](docs/proposta-tecnica.md)
- [Referências, versões e evidências](docs/referencias.md)
- [Procedimento de leitura no navegador](docs/piloto-leitura.md)

Não colocar cookies, snapshots pessoais ou bancos fora de `.local/` no Windows.
Não importar histórico nem copiar cookies de outros programas implicitamente.
Uma sessão `synced` significa valor observado igual ao proposto após releitura;
não há garantia de entrega exatamente uma vez ou de convergência com Playnite.
