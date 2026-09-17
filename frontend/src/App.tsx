import React from 'react';
import { ReactKeycloakProvider } from '@react-keycloak/web';
import Keycloak, { KeycloakConfig } from 'keycloak-js';
import ReportPage from './components/ReportPage';

const keycloakConfig: KeycloakConfig = {
  url: process.env.REACT_APP_KEYCLOAK_URL,
  realm: process.env.REACT_APP_KEYCLOAK_REALM||"",
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID||""
};

const keycloak = new Keycloak(keycloakConfig);

// PKCE: keycloak-js сам генерирует code_verifier, кладёт его в sessionStorage
// и отправляет code_challenge (S256) в authorization request.
// Вторая половина настройки на стороне Keycloak: у клиента reports-frontend
// в realm-export.json стоит pkce.code.challenge.method = S256,
// без challenge он авторизацию не начнёт.
const initOptions = {
  pkceMethod: 'S256' as const,
  checkLoginIframe: false,
};

const App: React.FC = () => {
  return (
    <ReactKeycloakProvider authClient={keycloak} initOptions={initOptions}>
      <div className="App">
        <ReportPage />
      </div>
    </ReactKeycloakProvider>
  );
};

export default App;