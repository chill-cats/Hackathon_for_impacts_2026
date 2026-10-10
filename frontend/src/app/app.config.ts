import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideIcons } from '@ng-icons/core';
import {
  lucideArrowRight,
  lucideBan,
  lucideCheck,
  lucideCircleAlert,
  lucideCircleDashed,
  lucideCircleHelp,
  lucideClock,
  lucideCloudOff,
  lucideDatabase,
  lucideDownload,
  lucideExternalLink,
  lucideFileText,
  lucideInfo,
  lucideMinus,
  lucideRefreshCw,
  lucideSearch,
  lucideSparkles,
  lucideTriangleAlert,
  lucideX,
} from '@ng-icons/lucide';
import { mockExampleInterceptor } from './core/api/mock-example.interceptor';
import { offlineDemoInterceptor } from './core/api/offline-demo.interceptor';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // Ordre : la démo hors ligne répond avant tout appel réseau ; le mock ne fait qu'ajouter l'en-tête Prefer.
    provideHttpClient(withInterceptors([offlineDemoInterceptor, mockExampleInterceptor])),
    provideIcons({
      lucideArrowRight,
      lucideBan,
      lucideCheck,
      lucideCircleAlert,
      lucideCircleDashed,
      lucideCircleHelp,
      lucideClock,
      lucideCloudOff,
      lucideDatabase,
      lucideDownload,
      lucideExternalLink,
      lucideFileText,
      lucideInfo,
      lucideMinus,
      lucideRefreshCw,
      lucideSearch,
      lucideSparkles,
      lucideTriangleAlert,
      lucideX,
    }),
  ],
};
