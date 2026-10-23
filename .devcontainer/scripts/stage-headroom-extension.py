#!/usr/bin/env python3
"""Package the dependency-free VS Code helper for Devsy's VSIX lifecycle."""

import io
import json
import os
from pathlib import Path
import tempfile
from xml.sax.saxutils import escape
import zipfile


def main():
    source = Path(__file__).resolve().parents[2] / ".vscode/headroom"
    package = json.loads((source / "package.json").read_text())
    cache = Path(os.environ.get("HEADROOM_VSIX_CACHE_DIR", Path.home() / ".cache/headroom"))
    target = cache / "work-jatt-headroom.vsix"
    manifest = f'''<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="{package['name']}" Version="{package['version']}" Publisher="{package['publisher']}" />
    <DisplayName>{escape(package['displayName'])}</DisplayName>
    <Description xml:space="preserve">{escape(package['description'])}</Description>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{package['engines']['vscode']}" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace" />
    </Properties>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code" /></Installation>
  <Dependencies />
  <Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" /></Assets>
</PackageManifest>'''
    content_types = '''<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="json" ContentType="application/json" />
  <Default Extension="js" ContentType="application/javascript" />
  <Default Extension="vsixmanifest" ContentType="text/xml" />
</Types>'''
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        files = {"extension.vsixmanifest": manifest.encode(), "[Content_Types].xml": content_types.encode()}
        files.update({f"extension/{name}": (source / name).read_bytes() for name in ("package.json", "extension.js")})
        for name, data in files.items():
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    cache.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.read_bytes() != payload.getvalue():
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as staged:
            temporary = Path(staged.name)
            try:
                staged.write(payload.getvalue())
                staged.close()
                temporary.chmod(0o644)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
    print(f"Staged Headroom VS Code setup: {target}")


if __name__ == "__main__":
    main()
