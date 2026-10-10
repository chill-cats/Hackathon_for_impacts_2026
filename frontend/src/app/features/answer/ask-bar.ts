import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { NgIcon } from '@ng-icons/core';
import { HlmButtonImports } from '@spartan-ng/helm/button';
import { HlmLabelImports } from '@spartan-ng/helm/label';
import { I18n } from '../../core/i18n/i18n';
import { AnswerStore } from '../../core/state/answer.store';
import { DEMO_QUESTIONS } from '../../core/state/demo-questions';

/**
 * Bloc 2 : la barre de question (un seul champ). Vide et sans réponse, elle propose les 5 questions test
 * du jury en exemples cliquables : la démo T01 → T05 se déroule sans rien taper.
 */
@Component({
  selector: 'app-ask-bar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgIcon, HlmButtonImports, HlmLabelImports],
  template: `
    <form class="flex flex-col gap-3" (submit)="$event.preventDefault(); submit()">
      <label hlmLabel for="question" class="sr-only">{{ i18n.t('ask.label') }}</label>
      <div
        class="border-input bg-surface focus-within:outline-focus flex items-center gap-2 rounded-md border py-1 pr-1 pl-3 focus-within:outline-2 focus-within:outline-offset-2"
      >
        <ng-icon name="lucideSearch" class="text-ink-muted text-base" aria-hidden="true" />
        <input
          id="question"
          name="question"
          autocomplete="off"
          class="text-foreground placeholder:text-muted-foreground min-w-0 flex-1 bg-transparent py-1.5 text-base outline-none"
          [placeholder]="i18n.t('ask.placeholder')"
          [value]="text()"
          (input)="text.set($any($event.target).value)"
        />
        <button hlmBtn type="submit" [disabled]="text().trim().length < 3">
          {{ i18n.t('ask.submit') }}
          <ng-icon name="lucideArrowRight" aria-hidden="true" />
        </button>
      </div>
    </form>

    @if (store.status() === 'idle' && text().trim().length === 0) {
      <div class="mt-3 flex flex-col gap-2" data-examples>
        <span class="type-caption text-ink-muted">{{ i18n.t('ask.examples') }}</span>
        <ul class="flex flex-col gap-2">
          @for (q of questions; track q.test) {
            <li>
              <button
                hlmBtn
                variant="secondary"
                size="sm"
                type="button"
                class="h-auto max-w-full justify-start py-1.5 text-left whitespace-normal"
                [attr.data-intent]="q.intent"
                (click)="ask(q.question[i18n.lang()], q.intent)"
              >
                <span class="type-code-sm text-ink-muted">{{ q.test }}</span>
                {{ q.question[i18n.lang()] }}
              </button>
            </li>
          }
        </ul>
      </div>
    }
  `,
})
export class AskBar {
  protected readonly store = inject(AnswerStore);
  protected readonly i18n = inject(I18n);

  protected readonly questions = DEMO_QUESTIONS;
  protected readonly text = signal('');

  constructor() {
    // La barre reflète la question de l'URL (lien partagé, précédent / suivant).
    effect(() => this.text.set(this.store.question()));
  }

  protected submit(): void {
    this.store.submit(this.text());
  }

  protected ask(question: string, intent: string): void {
    this.store.submit(question, { intent });
  }
}
