import { callable, definePlugin } from '@decky/api';
import { ButtonItem, PanelSection, PanelSectionRow } from '@decky/ui';
import { useEffect, useState } from 'react';

type Session = { id: string; app: string; elapsed: number; state: string; phase: string };
type Status = { sessions: Session[]; mode: string; auth: string; automatic: boolean };
const status = callable<[], Status>('status');
const labels: Record<string, string> = {
  local: 'Registrado localmente', pending: 'Pendente',
  synced: 'Sincronizado', attention: 'Precisa de atenção',
};

function Content() {
  const [data, setData] = useState<Status>();
  const [error, setError] = useState(false);
  const refresh = async () => {
    try { setData(await status()); setError(false); }
    catch { setError(true); }
  };
  useEffect(() => { void refresh(); }, []);
  return <PanelSection title="HLTB Sync for Deck">
    <PanelSectionRow>Protótipo local. Captura de jogos e login no Deck ainda não validados.</PanelSectionRow>
    <PanelSectionRow>Sincronização automática desativada.</PanelSectionRow>
    {error && <PanelSectionRow>Não foi possível ler as sessões locais.</PanelSectionRow>}
    <PanelSectionRow><ButtonItem onClick={refresh}>Atualizar sessões</ButtonItem></PanelSectionRow>
    {data?.sessions.map(s => <PanelSectionRow key={s.id}>
      App {s.app}: {Math.floor(s.elapsed)} s — {labels[s.state] ?? 'Precisa de atenção'}
    </PanelSectionRow>)}
  </PanelSection>;
}

export default definePlugin(() => ({
  name: 'HLTB Sync for Deck', title: <div>HLTB Sync for Deck</div>,
  content: <Content />, icon: <span>◷</span>, onDismount() {},
}));
