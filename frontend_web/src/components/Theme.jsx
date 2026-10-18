import { createContext, useContext, useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';

const ThemeContext = createContext({ theme: 'light' });
export const useTheme = () => useContext(ThemeContext);
export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('ds_appearance') === 'dark' ? 'dark' : 'light'; }
    catch { return 'light'; }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('ds_appearance', theme); } catch { /* Storage may be disabled. */ }
  }, [theme]);
  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
}
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return <button className="icon-button appearance-toggle" aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} appearance`} title={`Switch to ${theme === 'light' ? 'dark' : 'light'} appearance`} onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
    {theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}
  </button>;
}
