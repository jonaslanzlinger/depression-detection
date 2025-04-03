import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Socket } from 'ngx-socket-io';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  title = 'dashboard';
  audioData: any[] = [];

  constructor(private socket: Socket) {
    this.socket.fromEvent('audio_to_frontend').subscribe((data: any) => {
      this.audioData.unshift(data);
      if (this.audioData.length > 20) {
        this.audioData.pop();
      }
    });
  }
}
