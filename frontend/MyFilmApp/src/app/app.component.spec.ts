import { TestBed } from '@angular/core/testing';
import { MyFilmAppComponent } from './app.component';

describe('AppComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MyFilmAppComponent],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(MyFilmAppComponent);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it(`should have the 'MyFilmApp' title`, () => {
    const fixture = TestBed.createComponent(MyFilmAppComponent);
    const app = fixture.componentInstance;
    expect(app.title).toEqual('MyFilmApp');
  });

  it('should render title', () => {
    const fixture = TestBed.createComponent(MyFilmAppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Hello, MyFilmApp');
  });
});
