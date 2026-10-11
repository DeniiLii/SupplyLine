import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as RTooltip from "@radix-ui/react-tooltip";
import { Component, StrictMode, Suspense, lazy, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./design/global.css";
import { Layout } from "./components/Layout";
import { ThemeProvider } from "./components/theme";
import { Loading, ToastProvider } from "./components/ui";

const Simulator = lazy(() => import("./screens/Simulator"));
const Feed = lazy(() => import("./screens/Feed"));
const Overview = lazy(() => import("./screens/Overview"));
const Model = lazy(() => import("./screens/Model"));
const Market = lazy(() => import("./screens/Market"));
const About = lazy(() => import("./screens/About"));
const SupplierScreen = lazy(() => import("./screens/Supplier"));
const AnchorScreen = lazy(() => import("./screens/Anchor"));
const InvestorScreen = lazy(() => import("./screens/Investor"));

class Boundary extends Component<{ children: ReactNode }, { err: string | null }> {
  state = { err: null as string | null };
  static getDerivedStateFromError(e: Error) {
    return { err: e.message };
  }
  render() {
    if (this.state.err)
      return (
        <div role="alert" className="card">
          <h2 className="text-h2">Экран не отрисовался</h2>
          <p className="mt-2 text-small text-ink2">Ошибка интерфейса: {this.state.err}. Обновите страницу; если повторится — откройте другой экран из меню.</p>
        </div>
      );
    return this.props.children;
  }
}

const qc = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 5_000 } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={qc}>
        <RTooltip.Provider>
          <ToastProvider>
            <BrowserRouter>
              <Layout>
                <Boundary><Suspense fallback={<Loading rows={4} />}>
                  <Routes>
                    <Route path="/" element={<Navigate to="/simulator" replace />} />
                    <Route path="/simulator" element={<Simulator />} />
                    <Route path="/feed" element={<Feed />} />
                    <Route path="/feed/:id" element={<Feed />} />
                    <Route path="/overview" element={<Overview />} />
                    <Route path="/model" element={<Model />} />
                    <Route path="/market" element={<Market />} />
                    <Route path="/about" element={<About />} />
                    <Route path="/supplier" element={<SupplierScreen />} />
                    <Route path="/anchor" element={<AnchorScreen />} />
                    <Route path="/investor" element={<InvestorScreen />} />
                    <Route path="*" element={<Navigate to="/simulator" replace />} />
                  </Routes>
                </Suspense></Boundary>
              </Layout>
            </BrowserRouter>
          </ToastProvider>
        </RTooltip.Provider>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
