# Sondagem de leitura no Deck

Este procedimento está preparado, mas ainda não executado no Deck. Não instala
o plugin, não exporta cookies e não altera a conta.

1. Quando não estiver jogando, entre em `Power` → `Switch to Desktop`.
2. Abra o navegador e acesse `https://howlongtobeat.com`. Faça login diretamente
   no site. Nunca cole senha ou cookies no chat.
3. Na sua lista, abra a edição do registro **existente** do Vexx. Confira título,
   plataforma `PlayStation 2` e tempo. A URL esperada é `/submit/edit/<número>`.
   Não crie outra entrada. Se houver várias, escolha explicitamente a correta.
4. Leia `tools/browser-read-probe.js` antes de executá-lo em `Developer Tools` →
   `Console` nessa página. Ele apenas examina o JSON já presente no DOM e baixa
   `hltb-read-probe.private.json`; não faz requisição de envio. Não é necessário
   desabilitar proteções do navegador para esta fase; se a execução for bloqueada,
   interromper e diagnosticar.
5. Mantenha o arquivo privado. No Windows, guarde-o em `.local/`; no Deck, em
   diretório privado dedicado. O relatório tem título/plataforma/progresso e
   nomes dos campos, não o snapshot integral nem as credenciais.

O resultado prova apenas que a página autenticada expõe um registro reconhecido.
Não prova que o backend Python consegue autenticá-lo ou que `/api/submit` aceita
o formato atual. Não há botão de envio nesta versão. O próximo experimento será
definido com base no relatório e nas capacidades do navegador instalado.

SSH: usar a ponte existente, chave indicada pelo usuário, `BatchMode=yes`,
`HostKeyAlias=192.168.0.30` e `StrictHostKeyChecking=yes`. Não trocar/desabilitar
checagem de host; não executar comandos de instalação ou reinício. Confirmar
endereço e disponibilidade antes de conectar. Nenhuma chave é copiada ao repo.
