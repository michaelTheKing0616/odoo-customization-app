/** Inline theme bootstrap — runs before paint to avoid flash. */
export function ThemeScript() {
  const script = `(function(){try{var k='odoo-custom-theme';var s=localStorage.getItem(k);var n=new Date(),m=(n.getUTCHours()*60+n.getUTCMinutes()+60)%1440;var d=s==='dark'||(s==='sunset'?(m>=1120||m<400):(s!=='light'&&window.matchMedia('(prefers-color-scheme: dark)').matches));document.documentElement.classList.toggle('dark',d);}catch(e){}})();`;
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
