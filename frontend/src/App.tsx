import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import "./App.css";
import { AuthBanner } from "./components/AuthBanner";
import { AccessTokenPage } from "./pages/AccessTokenPage";
import { CallsLogPage } from "./pages/CallsLogPage";
import { CallbacksLogPage } from "./pages/CallbacksLogPage";
import { B2bBulkPage } from "./pages/B2bBulkPage";
import { B2cBulkPage } from "./pages/B2cBulkPage";
import { QrCodePage } from "./pages/QrCodePage";
import { RatibaPage } from "./pages/RatibaPage";
import { MaintainerClientsPage } from "./pages/MaintainerClientsPage";
import { MaintainerBusinessesPage } from "./pages/MaintainerBusinessesPage";
import { RegisterC2BPage } from "./pages/RegisterC2BPage";
import { StkErrorsLogPage } from "./pages/StkErrorsLogPage";
import { StkPushPage } from "./pages/StkPushPage";
import { TransactionsPage } from "./pages/TransactionsPage";

function App() {
  return (
    <div className='app'>
      <header className='app__header'>
        <div className='app__brand'>Mobile Money Dashboard</div>
        <nav className='app__nav'>
          <NavLink
            to='/token'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            Access Token
          </NavLink>
          <NavLink
            to='/stk'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            STK Push
          </NavLink>
          <NavLink
            to='/c2b/register'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            C2B Register
          </NavLink>
          <NavLink
            to='/transactions'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            Transactions
          </NavLink>
          <NavLink
            to='/b2c/bulk'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            B2C Bulk
          </NavLink>
          <NavLink
            to='/b2b/bulk'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            B2B Bulk
          </NavLink>
          <NavLink
            to='/qr'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            QR
          </NavLink>
          <NavLink
            to='/ratiba'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            Ratiba
          </NavLink>
          <NavLink
            to='/maintainer/clients'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            Maintainer
          </NavLink>
          <NavLink
            to='/maintainer/businesses'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            Businesses
          </NavLink>
          <NavLink
            to='/logs/calls'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            Call Logs
          </NavLink>
          <NavLink
            to='/logs/callbacks'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            Callback Logs
          </NavLink>
          <NavLink
            to='/logs/stk-errors'
            className={({ isActive }) =>
              isActive ? "nav__link nav__link--active" : "nav__link"
            }
          >
            STK Errors
          </NavLink>
        </nav>
      </header>

      <main className='app__main'>
        <AuthBanner />
        <Routes>
          <Route path='/' element={<Navigate to='/transactions' replace />} />
          <Route path='/token' element={<AccessTokenPage />} />
          <Route path='/stk' element={<StkPushPage />} />
          <Route path='/c2b/register' element={<RegisterC2BPage />} />
          <Route path='/transactions' element={<TransactionsPage />} />
          <Route path='/b2c/bulk' element={<B2cBulkPage />} />
          <Route path='/b2b/bulk' element={<B2bBulkPage />} />
          <Route path='/qr' element={<QrCodePage />} />
          <Route path='/ratiba' element={<RatibaPage />} />
          <Route
            path='/maintainer/clients'
            element={<MaintainerClientsPage />}
          />
          <Route
            path='/maintainer/businesses'
            element={<MaintainerBusinessesPage />}
          />
          <Route path='/logs/calls' element={<CallsLogPage />} />
          <Route path='/logs/callbacks' element={<CallbacksLogPage />} />
          <Route path='/logs/stk-errors' element={<StkErrorsLogPage />} />
          <Route path='*' element={<Navigate to='/transactions' replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
