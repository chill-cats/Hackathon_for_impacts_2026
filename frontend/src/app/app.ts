import { Component, DOCUMENT, inject, signal } from '@angular/core';
import { NgIcon, provideIcons } from '@ng-icons/core';
import {
  lucideCheck,
  lucideCircleHelp,
  lucideClock,
  lucideInfo,
  lucideMinus,
  lucideMoon,
  lucideSparkles,
  lucideSun,
  lucideTriangleAlert,
  lucideX,
} from '@ng-icons/lucide';
import { HlmAlertImports } from '@spartan-ng/helm/alert';
import { HlmBadgeImports, atlasStatus, type AtlasStatus } from '@spartan-ng/helm/badge';
import { HlmButtonImports } from '@spartan-ng/helm/button';
import { HlmCardImports } from '@spartan-ng/helm/card';
import { HlmInputImports } from '@spartan-ng/helm/input';
import { HlmLabelImports } from '@spartan-ng/helm/label';
import { HlmTableImports } from '@spartan-ng/helm/table';
import { HlmTabsImports } from '@spartan-ng/helm/tabs';

/** Icône associée à chaque variante de statut : un statut porte toujours une icône ET un mot. */
const STATUS_ICONS = {
  validated: 'lucideCheck',
  review: 'lucideCircleHelp',
  auto: 'lucideSparkles',
  rejected: 'lucideX',
  obsolete: 'lucideClock',
  unavailable: 'lucideMinus',
} as const;

/**
 * Planche de vérification du thème Atlas (Spartan + design system Atlas Homologations).
 * À retirer quand un vrai écran existe : elle ne sert qu'à contrôler visuellement les composants.
 */
@Component({
  selector: 'app-root',
  imports: [
    NgIcon,
    HlmAlertImports,
    HlmBadgeImports,
    HlmButtonImports,
    HlmCardImports,
    HlmInputImports,
    HlmLabelImports,
    HlmTableImports,
    HlmTabsImports,
  ],
  providers: [
    provideIcons({
      lucideCheck,
      lucideCircleHelp,
      lucideClock,
      lucideInfo,
      lucideMinus,
      lucideMoon,
      lucideSparkles,
      lucideSun,
      lucideTriangleAlert,
      lucideX,
    }),
  ],
  templateUrl: './app.html',
})
export class App {
  private readonly _document = inject(DOCUMENT);

  protected readonly title = signal('Homologations par pays');
  protected readonly dark = signal(false);

  protected readonly statuses = (Object.keys(atlasStatus) as AtlasStatus[]).map((key) => ({
    key,
    ...atlasStatus[key],
    icon: STATUS_ICONS[atlasStatus[key].variant],
  }));

  /** Bascule clair/sombre : `.dark` (Spartan) et `data-theme` (Atlas) sur <html>. */
  protected toggleTheme(): void {
    const dark = !this.dark();
    this.dark.set(dark);
    const root = this._document.documentElement;
    root.classList.toggle('dark', dark);
    root.dataset['theme'] = dark ? 'dark' : 'light';
  }
}
