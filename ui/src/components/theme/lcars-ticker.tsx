"use client";

import { useEffect, useState } from "react";

export function LCARSTicker() {
  const [ticker, setTicker] = useState("");

  useEffect(() => {
    const generateNumber = () => {
      const part1 = Math.floor(Math.random() * 90 + 10); // 2 digits
      const part2 = Math.floor(Math.random() * 900 + 100); // 3 digits
      return `${part1}-${part2}`;
    };

    setTicker(generateNumber());

    const interval = setInterval(() => {
      setTicker(generateNumber());
    }, 150); // fast strobe

    return () => clearInterval(interval);
  }, []);

  return (
    <span className="text-[9px] font-mono tracking-widest text-[var(--lcars-nav-text-on)] opacity-70 ml-auto tabular-nums">
      {ticker}
    </span>
  );
}
