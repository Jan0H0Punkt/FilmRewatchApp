import { Component } from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatToolbar } from '@angular/material/toolbar';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'mfa-root',
  imports: [RouterOutlet, MatToolbar, MatIcon, MatIconButton],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
}
