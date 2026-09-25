# `views/settings/`

The Settings view. A primary navigation destination; the app bar shows its
title.

So far one control: the FR-RW-08 rewatch-share `mat-slider`, 0% (new watches)
to 100% (rewatches) in steps of 10, saved on release via
`SettingsFacade.setRewatchShare`. A stored Off (`null`) shows as 100% — both
mean no cap. A failed save shows `SettingsFacade.error` as a `role="alert"`
line; the facade rolls the value back, so the thumb returns by itself — see
`domain/settings/facade.ts`.
