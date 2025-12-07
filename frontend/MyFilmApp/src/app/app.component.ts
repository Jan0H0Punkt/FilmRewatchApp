import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { BottomNavbarComponent } from './bottom-navbar/bottom-navbar.component';

@Component({
    selector: 'fm-root',
    standalone: true,
    imports: [RouterOutlet, BottomNavbarComponent],
    templateUrl: './app.component.html',
    styleUrl: './app.component.scss'
})
export class MyFilmAppComponent {
  title = 'MyFilmApp';
}
