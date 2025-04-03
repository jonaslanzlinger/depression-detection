import { bootstrapApplication } from '@angular/platform-browser';
import { importProvidersFrom } from '@angular/core';
import { AppComponent } from './app/app.component';
import { SocketIoModule, SocketIoConfig } from 'ngx-socket-io';

const config: SocketIoConfig = {
  url: 'http://localhost:5051',
  options: {},
};

bootstrapApplication(AppComponent, {
  providers: [importProvidersFrom(SocketIoModule.forRoot(config))],
}).catch((err) => console.error(err));
