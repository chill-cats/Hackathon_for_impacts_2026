import { Component, DOCUMENT, inject, signal } from '@angular/core';
import { NgIcon, provideIcons } from '@ng-icons/core';
import {
  lucideArrowRight,
  lucideCheck,
  lucideCircleHelp,
  lucideClock,
  lucideDownload,
  lucideExternalLink,
  lucideInfo,
  lucideMinus,
  lucideMoon,
  lucideSearch,
  lucideSparkles,
  lucideSun,
  lucideX,
} from '@ng-icons/lucide';
import { HlmAlertImports } from '@spartan-ng/helm/alert';
import { HlmBadgeImports, atlasStatus, type AtlasStatus } from '@spartan-ng/helm/badge';
import { HlmButtonImports } from '@spartan-ng/helm/button';
import { HlmCardImports } from '@spartan-ng/helm/card';
import { HlmInputImports } from '@spartan-ng/helm/input';
import { HlmLabelImports } from '@spartan-ng/helm/label';
import { HlmTableImports } from '@spartan-ng/helm/table';

/** Icône de chaque variante de statut : un statut porte toujours une icône ET un mot. */
const STATUS_ICONS = {
  validated: 'lucideCheck',
  review: 'lucideCircleHelp',
  auto: 'lucideSparkles',
  rejected: 'lucideX',
  obsolete: 'lucideClock',
  unavailable: 'lucideMinus',
} as const;

interface Country {
  code: string;
  authority: string;
}

interface Cell {
  dose: string;
  unit: string;
  status: AtlasStatus;
  cite: number;
}

interface UsageRow {
  id: string;
  crop: string;
  cropOriginal: string;
  cropEppo: string;
  target: string;
  targetOriginal: string;
  targetEppo: string;
  /** Une cellule absente (`null`) = « Non trouvé », jamais une preuve d'absence d'homologation. */
  cells: Record<string, Cell | null>;
}

interface Citation {
  n: number;
  sourceId: string;
  url: string;
  collectedAt: string;
  status: AtlasStatus;
  excerpt: string;
}

/**
 * Page de démo du design system Atlas Homologations : une mise en situation autour du produit pilote
 * LALSTOP G46 WG, comparé sur les trois pays du MVP. TOUTES les données ci-dessous sont fictives
 * (is_synthetic = true) et n'affirment aucune homologation réelle.
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
  ],
  providers: [
    provideIcons({
      lucideArrowRight,
      lucideCheck,
      lucideCircleHelp,
      lucideClock,
      lucideDownload,
      lucideExternalLink,
      lucideInfo,
      lucideMinus,
      lucideMoon,
      lucideSearch,
      lucideSparkles,
      lucideSun,
      lucideX,
    }),
  ],
  templateUrl: './app.html',
})
export class App {
  private readonly _document = inject(DOCUMENT);

  protected readonly dark = signal(false);
  protected readonly question = signal('');

  protected readonly hints = [
    'LALSTOP G46 WG est-il homologué sur tomate en France ?',
    'Comparer les doses de LALSTOP G46 WG entre le Canada et l’Allemagne',
    'Quels usages manquent en Allemagne ?',
  ];

  protected readonly countries: Country[] = [
    { code: 'CA', authority: 'Santé Canada · PPID' },
    { code: 'FR', authority: 'ANSES · E-Phy' },
    { code: 'DE', authority: 'BVL' },
  ];

  protected readonly rows: UsageRow[] = [
    {
      id: 'u1',
      crop: 'Tomate',
      cropOriginal: '« Tomato » (CA) · « Tomate » (FR)',
      cropEppo: 'LYPES',
      target: 'Pourriture grise',
      targetOriginal: '« Gray mold » (CA) · « Botrytis cinerea » (FR)',
      targetEppo: 'BOTRCI',
      cells: {
        CA: { dose: '1,5', unit: 'kg/ha', status: 'validated', cite: 1 },
        FR: { dose: '2,0', unit: 'kg/ha', status: 'validated', cite: 2 },
        DE: null,
      },
    },
    {
      id: 'u2',
      crop: 'Concombre',
      cropOriginal: '« Cucumber » (CA) · « Concombre » (FR)',
      cropEppo: 'CUCSA',
      target: 'Pourriture grise',
      targetOriginal: '« Gray mold » (CA) · « Botrytis cinerea » (FR)',
      targetEppo: 'BOTRCI',
      cells: {
        CA: { dose: '1,5', unit: 'kg/ha', status: 'to_verify', cite: 1 },
        FR: null,
        DE: null,
      },
    },
    {
      id: 'u3',
      crop: 'Fraise',
      cropOriginal: '« Strawberry » (CA) · « Fraisier » (FR)',
      cropEppo: 'FRAAN',
      target: 'Pourriture grise',
      targetOriginal: '« Gray mold » (CA) · « Botrytis cinerea » (FR)',
      targetEppo: 'BOTRCI',
      cells: {
        CA: { dose: '1,5', unit: 'kg/ha', status: 'validated', cite: 1 },
        FR: { dose: '2,0', unit: 'kg/ha', status: 'automatically_extracted', cite: 3 },
        DE: { dose: '—', unit: '', status: 'source_unavailable', cite: 4 },
      },
    },
  ];

  protected readonly citations: Citation[] = [
    {
      n: 1,
      sourceId: 'CA-PPID',
      url: '#',
      collectedAt: '2026-09-09T08:12:00Z',
      status: 'validated',
      excerpt: '« Tomato — Gray mold — 1.5 kg/ha » (valeur d’origine, démo)',
    },
    {
      n: 2,
      sourceId: 'FR-EPHY',
      url: '#',
      collectedAt: '2026-09-09T08:20:00Z',
      status: 'validated',
      excerpt: '« Tomate — Botrytis cinerea — 2 kg/ha » (valeur d’origine, démo)',
    },
    {
      n: 3,
      sourceId: 'FR-EPHY',
      url: '#',
      collectedAt: '2026-09-09T08:20:00Z',
      status: 'automatically_extracted',
      excerpt: '« Fraisier — Pourriture grise — 2 kg/ha » (extraction automatique, non relue)',
    },
    {
      n: 4,
      sourceId: 'DE-BVL',
      url: '#',
      collectedAt: '2026-09-09T08:31:00Z',
      status: 'source_unavailable',
      excerpt: 'L’API du BVL n’a pas répondu lors de cette collecte.',
    },
  ];

  protected readonly confidence = { value: 0.8, segments: [0, 1, 2, 3, 4] };

  protected readonly atlasStatus = atlasStatus;
  protected readonly statusIcons = STATUS_ICONS;

  protected pickHint(hint: string): void {
    this.question.set(hint);
  }

  protected badge(status: AtlasStatus): { variant: (typeof atlasStatus)[AtlasStatus]['variant']; label: string; icon: string } {
    const s = atlasStatus[status];
    return { variant: s.variant, label: s.label, icon: STATUS_ICONS[s.variant] };
  }

  /** Bascule clair/sombre : `.dark` (Spartan) et `data-theme` (Atlas) sur <html>. */
  protected toggleTheme(): void {
    const dark = !this.dark();
    this.dark.set(dark);
    const root = this._document.documentElement;
    root.classList.toggle('dark', dark);
    root.dataset['theme'] = dark ? 'dark' : 'light';
  }
}
