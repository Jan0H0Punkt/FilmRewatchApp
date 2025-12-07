import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { MyFilmAppComponent } from './app/app.component';

bootstrapApplication(MyFilmAppComponent, appConfig)
  .catch((err) => console.error(err));
