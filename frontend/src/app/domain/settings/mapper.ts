/** `SettingsDto` ↔ `Settings` (DESIGN §6.1). */
import type { SettingsDto } from './api';
import type { Settings } from './model';

export function toSettings(dto: SettingsDto): Settings {
  return { rewatchShare: dto.rewatch_share, watchIntervalDays: dto.watch_interval_days };
}

export function toSettingsDto(settings: Settings): SettingsDto {
  return { rewatch_share: settings.rewatchShare, watch_interval_days: settings.watchIntervalDays };
}
