import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import type { SourceInfo } from '../../core/api/models';
import { isMock, isOfflineDemo } from '../../core/api/runtime';
import { I18n } from '../../core/i18n/i18n';
import { AnswerStore } from '../../core/state/answer.store';

const DAY_MS = 24 * 60 * 60 * 1000;

interface SourceChip {
  source: SourceInfo;
  /** Orange : collecte de plus de 24 h, extrait figé ou source indisponible. */
  stale: boolean;
  note: string | null;
}

/**
 * Bloc 1 : nom de l'application, fraîcheur de chaque source (GET /sources), bascule FR / EN.
 * Les bandeaux « mock » et « démo hors ligne » rappellent que les données affichées sont fictives.
 */
@Component({
  selector: 'app-header',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon],
  template: `
    <div class="bg-brand h-[3px] w-full" aria-hidden="true"></div>
    @if (mock) {
      <div class="bg-status-review-soft text-status-review border-status-review-line border-b px-6 py-1 text-center text-xs font-semibold" role="status" data-banner="mock">
        {{ i18n.t('banner.mock') }}
      </div>
    }
    @if (offline) {
      <div class="bg-status-review-soft text-status-review border-status-review-line border-b px-6 py-1 text-center text-xs font-semibold" role="status" data-banner="offline">
        {{ i18n.t('banner.offline') }}
      </div>
    }
    <header class="bg-surface border-line border-b">
      <div class="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-3 px-6 py-3">
        <div class="flex items-baseline gap-3">
          <span class="type-display-m">LPC Regulatory Watch</span>
          <span class="type-caption text-ink-muted hidden sm:inline">Lallemand Plant Care</span>
        </div>

        <ul class="flex flex-wrap items-center gap-2" [attr.aria-label]="i18n.t('header.freshness')">
          @for (chip of chips(); track chip.source.sourceId) {
            <li
              class="type-code-sm inline-flex items-center gap-1 rounded-full border px-2 py-0.5"
              [class]="chip.stale ? 'border-status-review-line bg-status-review-soft text-status-review' : 'border-line text-ink-muted'"
              [attr.data-stale]="chip.stale"
              [attr.data-source]="chip.source.sourceId"
            >
              @if (chip.stale) {
                <ng-icon name="lucideClock" class="text-sm" aria-hidden="true" />
              }
              {{ chip.source.sourceId }} · {{ i18n.date(chip.source.lastCollectedAt) }}
              @if (chip.note) {
                <span class="font-semibold">· {{ chip.note }}</span>
              }
            </li>
          }
        </ul>

        <div class="border-line-strong inline-flex overflow-hidden rounded-md border" role="group" [attr.aria-label]="i18n.t('header.language')">
          @for (lang of languages; track lang) {
            <button
              type="button"
              class="aria-pressed:bg-primary aria-pressed:text-primary-foreground text-ink-strong hover:bg-surface-muted px-3 py-1 text-sm font-semibold uppercase"
              [attr.aria-pressed]="i18n.lang() === lang"
              [attr.lang]="lang"
              (click)="store.setLanguage(lang)"
            >
              {{ lang }}
            </button>
          }
        </div>
      </div>
    </header>
  `,
})
export class AppHeader {
  protected readonly i18n = inject(I18n);
  protected readonly store = inject(AnswerStore);

  protected readonly mock = isMock;
  protected readonly offline = isOfflineDemo;
  protected readonly languages = ['fr', 'en'] as const;

  protected readonly chips = computed<SourceChip[]>(() =>
    this.store
      .sources()
      // Les sources encore à valider (jamais collectées, sans disponibilité connue) n'ont rien à dire sur la fraîcheur.
      .filter((source) => source.lastCollectedAt || source.availability === 'unavailable')
      .map((source) => {
        const frozen = source.isFrozenExtract === true;
        const unavailable = source.availability === 'unavailable';
        const old = !source.lastCollectedAt || Date.now() - new Date(source.lastCollectedAt).getTime() > DAY_MS;
        const note = unavailable
          ? this.i18n.t('header.unavailable')
          : frozen
            ? this.i18n.t('header.frozen')
            : old
              ? this.i18n.t('header.older24h')
              : null;
        return { source, stale: frozen || unavailable || old, note };
      }),
  );
}
