/*
 * Copyright(c) 1997-2001 id Software, Inc.
 * Copyright(c) 2002 The Quakeforge Project.
 * Copyright(c) 2006 Quetoo.
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 *
 * See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

#include "cg_local.h"

#include "MeshViewController.h"

#define _Class _MeshViewController

#pragma mark - Internal helpers

/**
 * @brief Parses a mesh config file into raw transform components.
 */
static void ParseMeshConfigRaw(const char *path, cg_mesh_config_raw_t *raw) {

  raw->translate = Vec3_Zero();
  raw->rotate = Vec3_Zero();
  raw->scale = 1.f;
  raw->muzzle = Vec3_Zero();

  void *buf;
  if (cgi.LoadFile(path, &buf) == -1) {
    return;
  }

  parser_t parser = Parse_Init((const char *) buf, PARSER_DEFAULT);
  char token[MAX_STRING_CHARS];

  while (true) {

    if (!Parse_Token(&parser, PARSE_DEFAULT, token, sizeof(token))) {
      break;
    }

    if (!g_strcmp0(token, "translate")) {
      Parse_Primitive(&parser, PARSE_DEFAULT | PARSE_WITHIN_QUOTES | PARSE_NO_WRAP, PARSE_FLOAT, raw->translate.xyz, 3);
    } else if (!g_strcmp0(token, "rotate")) {
      Parse_Primitive(&parser, PARSE_DEFAULT | PARSE_WITHIN_QUOTES | PARSE_NO_WRAP, PARSE_FLOAT, raw->rotate.xyz, 3);
    } else if (!g_strcmp0(token, "scale")) {
      Parse_Primitive(&parser, PARSE_DEFAULT | PARSE_WITHIN_QUOTES | PARSE_NO_WRAP, PARSE_FLOAT, &raw->scale, 1);
    } else if (!g_strcmp0(token, "muzzle")) {
      Parse_Primitive(&parser, PARSE_DEFAULT | PARSE_WITHIN_QUOTES | PARSE_NO_WRAP, PARSE_FLOAT, raw->muzzle.xyz, 3);
    }
  }

  cgi.FreeFile(buf);
}

/**
 * @brief Builds a mat4_t transform from raw config components.
 */
static mat4_t MeshConfigTransform(const cg_mesh_config_raw_t *raw) {

  mat4_t m = Mat4_Identity();
  m = Mat4_ConcatTranslation(m, raw->translate);
  m = Mat4_ConcatRotation3(m, raw->rotate);
  m = Mat4_ConcatScale(m, raw->scale);
  return m;
}

#pragma mark - Delegates

/**
 * @brief SliderDelegate callback — update raw components and reapply transform live.
 */
static void didSetValue(Slider *slider, double value) {

  MeshViewController *this = (MeshViewController *) slider->delegate.self;

  if (!this->model) {
    return;
  }

  if (slider == this->worldTranslateX) {
    this->world.translate.x = (float) value;
  } else if (slider == this->worldTranslateY) {
    this->world.translate.y = (float) value;
  } else if (slider == this->worldTranslateZ) {
    this->world.translate.z = (float) value;
  } else if (slider == this->worldRotateX) {
    this->world.rotate.x = (float) value;
  } else if (slider == this->worldRotateY) {
    this->world.rotate.y = (float) value;
  } else if (slider == this->worldRotateZ) {
    this->world.rotate.z = (float) value;
  } else if (slider == this->worldScale) {
    this->world.scale = (float) value;
  } else {
    Cg_Debug("Unknown slider %p\n", (void *) slider);
    return;
  }

  this->model->mesh->config.world.transform = MeshConfigTransform(&this->world);
}

#pragma mark - ViewController

/**
 * @see ViewController::loadView(ViewController *)
 */
static void loadView(ViewController *self) {

  super(ViewController, self, loadView);

  MeshViewController *this = (MeshViewController *) self;

  Outlet outlets[] = MakeOutlets(
    MakeOutlet("worldTranslateX", &this->worldTranslateX),
    MakeOutlet("worldTranslateY", &this->worldTranslateY),
    MakeOutlet("worldTranslateZ", &this->worldTranslateZ),
    MakeOutlet("worldRotateX",    &this->worldRotateX),
    MakeOutlet("worldRotateY",    &this->worldRotateY),
    MakeOutlet("worldRotateZ",    &this->worldRotateZ),
    MakeOutlet("worldScale",      &this->worldScale)
  );

  $(self->view, awakeWithResourceName, "ui/editor/MeshViewController.json");
  $(self->view, resolve, outlets);

  self->view->stylesheet = $$(Stylesheet, stylesheetWithResourceName, "ui/editor/MeshViewController.css");

  Slider *sliders[] = {
    this->worldTranslateX, this->worldTranslateY, this->worldTranslateZ,
    this->worldRotateX, this->worldRotateY, this->worldRotateZ,
    this->worldScale,
  };

  for (size_t i = 0; i < lengthof(sliders); i++) {
    sliders[i]->delegate.self = self;
    sliders[i]->delegate.didSetValue = didSetValue;
  }
}

/**
 * @see ViewController::viewWillAppear(ViewController *)
 */
static void viewWillAppear(ViewController *self) {

  MeshViewController *this = (MeshViewController *) self;

  r_model_t *model = NULL;

  if (cg_editor.selected > 0) {
    const cg_editor_entity_t *edit = &cg_editor.entities[cg_editor.selected];
    if (edit->model && IS_MESH_MODEL(edit->model)) {
      model = (r_model_t *) edit->model;
    }
  }

  $(this, setModel, model);

  super(ViewController, self, viewWillAppear);
}

#pragma mark - MeshViewController

/**
 * @fn MeshViewController *MeshViewController::init(MeshViewController *self)
 * @memberof MeshViewController
 */
static MeshViewController *init(MeshViewController *self) {
  return (MeshViewController *) super(ViewController, self, init);
}

/**
 * @fn void MeshViewController::setModel(MeshViewController *self, r_model_t *model)
 * @memberof MeshViewController
 */
static void setModel(MeshViewController *self, r_model_t *model) {

  self->model = model;

  if (self->model) {

    char path[MAX_QPATH];
    Dirname(self->model->media.name, path);

    ParseMeshConfigRaw(va("%s/world.cfg", path), &self->world);

    $(self->worldTranslateX, setValue, (double) self->world.translate.x);
    $(self->worldTranslateY, setValue, (double) self->world.translate.y);
    $(self->worldTranslateZ, setValue, (double) self->world.translate.z);
    $(self->worldRotateX,    setValue, (double) self->world.rotate.x);
    $(self->worldRotateY,    setValue, (double) self->world.rotate.y);
    $(self->worldRotateZ,    setValue, (double) self->world.rotate.z);
    $(self->worldScale,      setValue, (double) self->world.scale);

  } else {

    self->world = (cg_mesh_config_raw_t) { .scale = 1.f };

    $(self->worldTranslateX, setValue, 0.0);
    $(self->worldTranslateY, setValue, 0.0);
    $(self->worldTranslateZ, setValue, 0.0);
    $(self->worldRotateX,    setValue, 0.0);
    $(self->worldRotateY,    setValue, 0.0);
    $(self->worldRotateZ,    setValue, 0.0);
    $(self->worldScale,      setValue, 1.0);
  }
}

/**
 * @fn void MeshViewController::save(MeshViewController *self)
 * @memberof MeshViewController
 */
static void save(MeshViewController *self) {

  if (!self->model) {
    return;
  }

  char dir[MAX_QPATH];
  Dirname(self->model->media.name, dir);

  const char *path = va("%s/world.cfg", dir);
  file_t *file = cgi.OpenFileWrite(path);
  if (file) {

    char line[MAX_STRING_CHARS];
    size_t len;

    if (!Vec3_Equal(self->world.translate, Vec3_Zero())) {
      len = (size_t) g_snprintf(line, sizeof(line), "translate %g %g %g\n",
                                self->world.translate.x, self->world.translate.y, self->world.translate.z);
      cgi.WriteFile(file, line, 1, len);
    }

    if (!Vec3_Equal(self->world.rotate, Vec3_Zero())) {
      len = (size_t) g_snprintf(line, sizeof(line), "rotate %g %g %g\n",
                                self->world.rotate.x, self->world.rotate.y, self->world.rotate.z);
      cgi.WriteFile(file, line, 1, len);
    }

    if (self->world.scale != 1.f) {
      len = (size_t) g_snprintf(line, sizeof(line), "scale %g\n", self->world.scale);
      cgi.WriteFile(file, line, 1, len);
    }

    cgi.CloseFile(file);
    Cg_Debug("Wrote %s\n", path);

  } else {
    Cg_Warn("Failed to write %s\n", path);
  }
}

#pragma mark - Class lifecycle

/**
 * @see Class::initialize(Class *)
 */
static void initialize(Class *clazz) {

  ((ViewControllerInterface *) clazz->interface)->loadView = loadView;
  ((ViewControllerInterface *) clazz->interface)->viewWillAppear = viewWillAppear;

  ((MeshViewControllerInterface *) clazz->interface)->init = init;
  ((MeshViewControllerInterface *) clazz->interface)->setModel = setModel;
  ((MeshViewControllerInterface *) clazz->interface)->save = save;
}

/**
 * @fn Class *MeshViewController::_MeshViewController(void)
 * @memberof MeshViewController
 */
Class *_MeshViewController(void) {
  static Class *clazz;
  static Once once;

  do_once(&once, {
    clazz = _initialize(&(const ClassDef) {
      .name = "MeshViewController",
      .superclass = _ViewController(),
      .instanceSize = sizeof(MeshViewController),
      .interfaceOffset = offsetof(MeshViewController, interface),
      .interfaceSize = sizeof(MeshViewControllerInterface),
      .initialize = initialize,
    });
  });

  return clazz;
}

#undef _Class
