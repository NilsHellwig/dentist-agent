"use client";

import { CallScreen } from "@/components/CallScreen";
import { StartScreen } from "@/components/StartScreen";
import { useCall } from "@/lib/useCall";

export default function Home() {
  const call = useCall();

  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col px-6 py-10">
      {call.phase === "idle" || call.phase === "connecting" ? (
        <StartScreen connecting={call.phase === "connecting"} error={call.error} onStart={call.start} />
      ) : (
        <CallScreen call={call} />
      )}
    </main>
  );
}
