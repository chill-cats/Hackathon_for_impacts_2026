import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { HlmButtonImports } from '@spartan-ng/helm/button';

@Component({
  imports: [RouterOutlet, HlmButtonImports],
  selector: 'app-root',
  templateUrl: './app.html',
})
export class App {
  protected readonly title = signal('Hackathon Lallemand');
  protected readonly clicks = signal(0);
}
