# Validacao Linux Packaging (R7.5.3)

Data: 2026-02-16

## Artefatos gerados

- `dist/git-viewer_0.2.0_amd64.deb`
- `dist/git-viewer-0.2.0-x86_64.AppImage`

## Validacao `.deb` (instalacao/remocao)

Ambiente sem `sudo` passwordless. Foi executada validacao real de install/remove em raiz isolada via `dpkg`:

```bash
TMPROOT="$(mktemp -d)"
mkdir -p "$TMPROOT/var/lib/dpkg"
: > "$TMPROOT/var/lib/dpkg/status"

dpkg --log="$TMPROOT/dpkg.log" \
  --root="$TMPROOT" \
  --instdir="$TMPROOT" \
  --admindir="$TMPROOT/var/lib/dpkg" \
  --force-not-root --force-bad-path --force-depends \
  --install dist/git-viewer_0.2.0_amd64.deb

"$TMPROOT/opt/git-viewer/git_viewer" --help

dpkg --log="$TMPROOT/dpkg.log" \
  --root="$TMPROOT" \
  --instdir="$TMPROOT" \
  --admindir="$TMPROOT/var/lib/dpkg" \
  --force-not-root --force-bad-path --force-depends \
  --remove git-viewer

rm -rf "$TMPROOT"
```

Resultado:
- install OK;
- launcher e desktop entry presentes;
- binario executando (`--help`);
- remove OK.

## Validacao AppImage

Sem `libfuse.so.2` no host, validado com fallback de extracao:

```bash
APPIMAGE_EXTRACT_AND_RUN=1 ./dist/git-viewer-0.2.0-x86_64.AppImage --help
```

Resultado:
- AppImage executa e responde `--help`.

## Observacoes

- Em desktops sem FUSE2, executar AppImage com `APPIMAGE_EXTRACT_AND_RUN=1`.
- Para validacao de menu via `.deb` no host real (fora raiz isolada), usar:
  - `sudo dpkg -i dist/git-viewer_0.2.0_amd64.deb`
  - `sudo dpkg -r git-viewer`
