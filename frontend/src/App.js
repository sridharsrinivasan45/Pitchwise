import { BrowserRouter, Routes, Route } from "react-router-dom";
import TopNav from "@/components/layout/TopNav";
import Live from "@/pages/Live";
import TimeMachine from "@/pages/TimeMachine";
import Players from "@/pages/Players";
import PlayerProfile from "@/pages/PlayerProfile";
import About from "@/pages/About";
import "@/App.css";

function App() {
  return (
    <div className="min-h-screen bg-background text-foreground font-sans" data-testid="app-root">
      <BrowserRouter>
        <TopNav />
        <main className="pt-20">
          <Routes>
            <Route path="/" element={<Live />} />
            <Route path="/time-machine" element={<TimeMachine />} />
            <Route path="/players" element={<Players />} />
            <Route path="/players/:id" element={<PlayerProfile />} />
            <Route path="/about" element={<About />} />
          </Routes>
        </main>
      </BrowserRouter>
    </div>
  );
}

export default App;
