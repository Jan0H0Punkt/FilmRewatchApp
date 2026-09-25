/** `SettingsDto` ↔ `Settings` (DESIGN §6.1). */
import type { SettingsDto } from './api';
import type { Settings } from './model';

export function toSettings(dto: SettingsDto): Settings {
  return { rewatchShare: dto.rewatch_share };
}

export function toSettingsDto(rewatchShare: number | null): SettingsDto {
  return { rewatch_share: rewatchShare };
}
