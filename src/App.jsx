import "./App.css";
import { RouterProvider, createBrowserRouter, Outlet } from "react-router-dom";
import LandingPage from "./pages/landing";

// AppLayout component to wrap all routes
function AppLayout() {
  return (
    <div className="min-h-screen">
      <Outlet />
    </div>
  );
}

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      {
        path: "/",
        element: <LandingPage />,
      },
    ],
  },
]);

function App() {
  return <RouterProvider router={router} />;
}

export default App;
