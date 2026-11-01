# Third-party notices

Everything in this repository was written for this project, except the items below.

| What | Where | Used for | Licence |
|---|---|---|---|
| DejaVu Sans font (`DejaVuSans.ttf`), from the DejaVu fonts project | [examples/northbound/northbound/fonts/](examples/northbound/northbound/fonts/) | the Northbound demo app's itinerary PDF | Bitstream Vera Fonts licence (with the Arev fonts licence for its imported glyphs); DejaVu changes are in the public domain. Full text: [LICENSE_DEJAVU](examples/northbound/northbound/fonts/LICENSE_DEJAVU), shipped beside the font |

**Dependencies.** The Python packages named in [pyproject.toml](pyproject.toml) (for example pydantic, typer,
Playwright, Jinja2, FastAPI) and the Chromium build that Playwright downloads are installed from their own sources
under their own licences. None of their code is copied into this repository.

**Apps under test.** Spree and Finablo are not in this repository. Spree is driven through its own harness repo,
[spree-semaudit](https://github.com/jaykay2000/spree-semaudit); Finablo is the author's own app and appears only in
evidence and demo frames.
