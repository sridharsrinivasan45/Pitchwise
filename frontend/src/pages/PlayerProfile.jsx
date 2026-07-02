import { useParams } from "react-router-dom";

export default function PlayerProfile() {
  const { id } = useParams();
  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10" data-testid="player-profile-page">
      <p className="text-dim text-[11px] uppercase tracking-widest mb-3">Player</p>
      <h1 className="font-editorial text-4xl mb-2">{id}</h1>
      <p className="text-muted-foreground">Detailed profile lands in the Player Profile milestone.</p>
    </div>
  );
}
