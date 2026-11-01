import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Praxis Nordlicht – Sprachassistenz",
    short_name: "Nordlicht",
    description: "Sprachassistenz der Zahnarztpraxis Nordlicht",
    start_url: "/",
    display: "standalone",
    background_color: "#f5f2ec",
    theme_color: "#f5f2ec",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
