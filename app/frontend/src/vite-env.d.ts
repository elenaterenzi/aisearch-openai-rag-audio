/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_USE_VOICE_LIVE: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}
